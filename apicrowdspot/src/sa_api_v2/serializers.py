"""
DjangoRestFramework resources for the Shareabouts REST API.
"""
import ujson as json
import re
from itertools import chain
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ValidationError
from rest_framework import pagination
from rest_framework import serializers
from rest_framework.reverse import reverse

from . import models
from .models import check_data_permission
from .params import (INCLUDE_INVISIBLE_PARAM, INCLUDE_PRIVATE_PARAM,
    INCLUDE_SUBMISSIONS_PARAM, FORMAT_PARAM)

import logging
log = logging.getLogger(__name__)


###############################################################################
#
# Geo-related fields
# ------------------
#

class GeometryField(serializers.WritableField):
    def __init__(self, format='dict', *args, **kwargs):
        self.format = format

        if self.format not in ('json', 'wkt', 'dict'):
            raise ValueError('Invalid format: %s' % self.format)

        super(GeometryField, self).__init__(*args, **kwargs)

    def to_native(self, obj):
        if self.format == 'json':
            return obj.json
        elif self.format == 'wkt':
            return obj.wkt
        elif self.format == 'dict':
            return json.loads(obj.json)
        else:
            raise ValueError('Cannot output as %s' % self.format)

    def from_native(self, data):
        if not isinstance(data, basestring):
            data = json.dumps(data)

        try:
            return GEOSGeometry(data)
        except Exception as exc:
            raise ValidationError('Problem converting native data to Geometry: %s' % (exc,))

###############################################################################
#
# Shareabouts-specific fields
# ---------------------------
#

class ShareaboutsFieldMixin (object):

    # These names should match the names of the cache parameters, and should be
    # in the same order as the corresponding URL arguments.
    url_arg_names = ()

    def get_url_kwargs(self, obj):
        """
        Pull the appropriate arguments off of the cache to construct the URL.
        """
        if isinstance(obj, models.User):
            instance_kwargs = {'owner_username': obj.username}
        else:
            instance_kwargs = obj.cache.get_cached_instance_params(obj.pk, lambda: obj)

        url_kwargs = {}
        for arg_name in self.url_arg_names:
            arg_value = instance_kwargs.get(arg_name, None)
            if arg_value is None:
                try:
                    arg_value = getattr(obj, arg_name)
                except AttributeError:
                    raise KeyError('No arg named %r in %r' % (arg_name, instance_kwargs))
            url_kwargs[arg_name] = arg_value
        return url_kwargs


class ShareaboutsRelatedField (ShareaboutsFieldMixin, serializers.HyperlinkedRelatedField):
    """
    Represents a Shareabouts relationship using hyperlinking.
    """
    read_only = True
    view_name = None

    def __init__(self, *args, **kwargs):
        if self.view_name is not None:
            kwargs['view_name'] = self.view_name
        super(ShareaboutsRelatedField, self).__init__(*args, **kwargs)

    def to_native(self, obj):
        view_name = self.view_name
        request = self.context.get('request', None)
        format = self.format or self.context.get('format', None)

        pk = getattr(obj, 'pk', None)
        if pk is None:
            return

        kwargs = self.get_url_kwargs(obj)
        return reverse(view_name, kwargs=kwargs, request=request, format=format)


class DataSetRelatedField (ShareaboutsRelatedField):
    view_name = 'dataset-detail'
    url_arg_names = ('owner_username', 'dataset_slug')


class DataSetKeysRelatedField (ShareaboutsRelatedField):
    view_name = 'apikey-list'
    url_arg_names = ('owner_username', 'dataset_slug')


class UserRelatedField (ShareaboutsRelatedField):
    view_name = 'user-detail'
    url_arg_names = ('owner_username',)


class PlaceRelatedField (ShareaboutsRelatedField):
    view_name = 'place-detail'
    url_arg_names = ('owner_username', 'dataset_slug', 'place_id')


class SubmissionSetRelatedField (ShareaboutsRelatedField):
    view_name = 'submission-list'
    url_arg_names = ('owner_username', 'dataset_slug', 'place_id', 'submission_set_name')


class ShareaboutsIdentityField (ShareaboutsFieldMixin, serializers.HyperlinkedIdentityField):
    read_only = True

    def __init__(self, *args, **kwargs):
        view_name = kwargs.pop('view_name', None) or getattr(self, 'view_name', None)
        super(ShareaboutsIdentityField, self).__init__(view_name=view_name, *args, **kwargs)

    def field_to_native(self, obj, field_name):
        if obj.pk is None: return None

        request = self.context.get('request', None)
        format = self.context.get('format', None)
        view_name = self.view_name or self.parent.opts.view_name

        kwargs = self.get_url_kwargs(obj)

        if format and self.format and self.format != format:
            format = self.format

        return reverse(view_name, kwargs=kwargs, request=request, format=format)


class PlaceIdentityField (ShareaboutsIdentityField):
    url_arg_names = ('owner_username', 'dataset_slug', 'place_id')


class SubmissionSetIdentityField (ShareaboutsIdentityField):
    url_arg_names = ('owner_username', 'dataset_slug', 'place_id', 'submission_set_name')
    view_name = 'submission-list'


class DataSetPlaceSetIdentityField (ShareaboutsIdentityField):
    url_arg_names = ('owner_username', 'dataset_slug')
    view_name = 'place-list'


class DataSetSubmissionSetIdentityField (ShareaboutsIdentityField):
    url_arg_names = ('owner_username', 'dataset_slug', 'submission_set_name')
    view_name = 'dataset-submission-list'


class SubmissionIdentityField (ShareaboutsIdentityField):
    url_arg_names = ('owner_username', 'dataset_slug', 'place_id', 'submission_set_name', 'submission_id')


class DataSetIdentityField (ShareaboutsIdentityField):
    url_arg_names = ('owner_username', 'dataset_slug')


class AttachmentFileField (serializers.FileField):
    def to_native(self, obj):
        return obj.storage.url(obj.name)


###############################################################################
#
# Serializer Mixins
# -----------------
#


class ActivityGenerator (object):
    def save(self, **kwargs):
        request = self.context['request']
        silent_header = request.META.get('HTTP_X_SHAREABOUTS_SILENT', 'False')
        is_silent = silent_header.lower() in ('true', 't', 'yes', 'y')
        request_source = request.META.get('HTTP_REFERER', '')
        return super(ActivityGenerator, self).save(silent=is_silent, source=request_source, **kwargs)


class EmptyModelSerializer (object):
    """
    A simple mixin that constructs an in-memory model when None is passed in
    as the object to to_native.
    """
    def ensure_obj(self, obj):
        if obj is None: obj = self.opts.model()
        return obj


class DataBlobProcessor (EmptyModelSerializer):
    """
    Like ModelSerializer, but automatically serializes/deserializes a
    'data' JSON blob of arbitrary key/value pairs.
    """

    def convert_object(self, obj):
        attrs = super(DataBlobProcessor, self).convert_object(obj)

        data = json.loads(obj.data)
        del attrs['data']
        attrs.update(data)

        return attrs

    def restore_fields(self, data, files):
        """
        Converts a dictionary of data into a dictionary of deserialized fields.
        """
        model = self.opts.model
        blob = {}
        data_copy = {}

        # Pull off any fields that the model doesn't know about directly
        # and put them into the data blob.
        known_fields = set(model._meta.get_all_field_names())

        # Also ignore the following field names (treat them like reserved
        # words).
        known_fields.update(self.base_fields.keys())

        # And allow an arbitrary value field named 'data' (don't let the
        # data blob get in the way).
        known_fields.remove('data')

        for key in data:
            if key in known_fields:
                data_copy[key] = data[key]
            else:
                blob[key] = data[key]

        data_copy['data'] = json.dumps(blob)

        if not self.partial:
            for field_name, field in self.base_fields.items():
                if (not field.read_only and field_name not in data_copy):
                    data_copy[field_name] = field.default

        return super(DataBlobProcessor, self).restore_fields(data_copy, files)

    def explode_data_blob(self, data):
        blob = data.pop('data')

        blob_data = json.loads(blob)
        request = self.context['request']

        # Did the user not ask for private data? Remove it!
        if INCLUDE_PRIVATE_PARAM not in request.GET:
            for key in blob_data.keys():
                if key.startswith('private'):
                    del blob_data[key]

        data.update(blob_data)
        return data

    def to_native(self, obj):
        obj = self.ensure_obj(obj)
        data = super(DataBlobProcessor, self).to_native(obj)
        self.explode_data_blob(data)
        return data


###############################################################################
#
# User Data Strategies
# --------------------
# Shims for reading user data from various social authentication provider
# objects.
#

class DefaultUserDataStrategy (object):
    def extract_avatar_url(self, user_info):
        return ''

    def extract_full_name(self, user_info):
        return ''

    def extract_bio(self, user_info):
        return ''


class TwitterUserDataStrategy (object):
    def extract_avatar_url(self, user_info):
        url = user_info['profile_image_url']

        url_pattern = '^(?P<path>.*?)(?:_normal|_mini|_bigger|)(?P<ext>\.[^\.]*)$'
        match = re.match(url_pattern, url)
        if match:
            return match.group('path') + '_bigger' + match.group('ext')
        else:
            return url

    def extract_full_name(self, user_info):
        return user_info['name']

    def extract_bio(self, user_info):
        return user_info['description']


class FacebookUserDataStrategy (object):
    def extract_avatar_url(self, user_info):
        url = user_info['picture']['data']['url']
        return url

    def extract_full_name(self, user_info):
        return user_info['name']

    def extract_bio(self, user_info):
        return user_info['bio']


class ShareaboutsUserDataStrategy (object):
    """
    This strategy exists so that we can add avatars and full names to users
    that already exist in the system without them creating a Twitter or
    Facebook account.
    """
    def extract_avatar_url(self, user_info):
        return user_info.get('avatar_url', None)

    def extract_full_name(self, user_info):
        return user_info.get('full_name', None)

    def extract_bio(self, user_info):
        return user_info.get('bio', None)


###############################################################################
#
# Serializers
# -----------
#

class GroupSerializer (serializers.ModelSerializer):
    dataset = DataSetRelatedField()

    class Meta:
        model = models.Group
        exclude = ('submitters', 'id')


class UserSerializer (serializers.ModelSerializer):
    name = serializers.SerializerMethodField('get_name')
    avatar_url = serializers.SerializerMethodField('get_avatar_url')
    groups = GroupSerializer(many=True, source='_groups', read_only=True)

    strategies = {
        'twitter': TwitterUserDataStrategy(),
        'facebook': FacebookUserDataStrategy(),
        'shareabouts': ShareaboutsUserDataStrategy()
    }
    default_strategy = DefaultUserDataStrategy()

    class Meta:
        model = models.User
        exclude = ('first_name', 'last_name', 'email', 'password', 'is_staff', 'is_active', 'is_superuser', 'last_login', 'date_joined', 'user_permissions')

    def get_strategy(self, obj):
        for social_auth in obj.social_auth.all():
            provider = social_auth.provider
            if provider in self.strategies:
                return social_auth.extra_data, self.strategies[provider]

        return None, self.default_strategy

    def get_name(self, obj):
        user_data, strategy = self.get_strategy(obj)
        return strategy.extract_full_name(user_data)

    def get_avatar_url(self, obj):
        user_data, strategy = self.get_strategy(obj)
        return strategy.extract_avatar_url(user_data)


class SubmissionSetSummarySerializer (EmptyModelSerializer, serializers.HyperlinkedModelSerializer):
    length = serializers.IntegerField()
    url = SubmissionSetIdentityField()

    class Meta:
        model = models.SubmissionSet
        fields = ('length', 'url')

    def to_native(self, obj):
        obj = self.ensure_obj(obj)
        return {
            'length': obj.length,
            'url': self.fields['url'].field_to_native(obj, 'url')
        }


class DataSetPlaceSetSummarySerializer (serializers.HyperlinkedModelSerializer):
    length = serializers.IntegerField(source='places_length')
    url = DataSetPlaceSetIdentityField()

    class Meta:
        model = models.DataSet
        fields = ('length', 'url')

    def to_native(self, obj):
        place_count_map = self.context['place_count_map_getter']()
        obj.places_length = place_count_map.get(obj.pk, 0)
        data = super(DataSetPlaceSetSummarySerializer, self).to_native(obj)
        return data


class DataSetSubmissionSetSummarySerializer (serializers.HyperlinkedModelSerializer):
    length = serializers.IntegerField(source='submission_set_length')
    url = DataSetSubmissionSetIdentityField()

    class Meta:
        model = models.DataSet
        fields = ('length', 'url')

    def to_native(self, obj):
        request = self.context['request']
        submission_sets_map = self.context['submission_sets_map_getter']()
        sets = submission_sets_map.get(obj.id, {})
        summaries = {}
        for submission_set in sets:
            set_name = submission_set['parent__name']

            # Ensure the user has read permission on the submission set.
            user = getattr(request, 'user', None)
            client = getattr(request, 'client', None)
            dataset = obj
            if not check_data_permission(user, client, 'retrieve', dataset, set_name):
                continue

            obj.submission_set_name = set_name
            obj.submission_set_length = submission_set['length']
            summaries[set_name] = super(DataSetSubmissionSetSummarySerializer, self).to_native(obj)
        return summaries


class SubmittedThingSerializer (ActivityGenerator, DataBlobProcessor):
    def restore_fields(self, data, files):
        """
        Converts a dictionary of data into a dictionary of deserialized fields.
        """
        result = super(SubmittedThingSerializer, self).restore_fields(data, files)

        if 'submitter' not in data:
            # If the thing exists already, use the existing submitter
            if hasattr(self, 'object') and self.object is not None:
                result['submitter'] = self.object.submitter

            # Otherwise, set the submitter to the current user
            else:
                request = self.context.get('request')
                if request and request.user.is_authenticated():
                    result['submitter'] = request.user

        return result


class AttachmentSerializer (serializers.ModelSerializer):
    file = AttachmentFileField()

    class Meta:
        model = models.Attachment
        exclude = ('id', 'thing',)

    def to_native(self, obj):
        if obj is None: obj = models.Attachment()
        return {
            'created_datetime': obj.created_datetime,
            'updated_datetime': obj.updated_datetime,
            'file': obj.file.storage.url(obj.file.name),
            'name': obj.name
        }


class PlaceSerializer (SubmittedThingSerializer, serializers.HyperlinkedModelSerializer):
    url = PlaceIdentityField()
    id = serializers.PrimaryKeyRelatedField(read_only=True)
    geometry = GeometryField(format='wkt')
    dataset = DataSetRelatedField()
    attachments = AttachmentSerializer(read_only=True, many=True)
    submitter = UserSerializer(read_only=False)

    class Meta:
        model = models.Place

    def get_submission_set_summaries(self, place):
        """
        Get a mapping from place id to a submission set summary dictionary.
        Get this for the entire dataset at once.
        """
        request = self.context['request']
        include_invisible = INCLUDE_INVISIBLE_PARAM in request.GET

        summaries = {}
        for submission_set in place.submission_sets.all():
            # Ensure the user has read permission on the submission set.
            user = getattr(request, 'user', None)
            client = getattr(request, 'client', None)
            dataset = getattr(request, 'get_dataset', lambda: None)()
            if not check_data_permission(user, client, 'retrieve', dataset, submission_set):
                continue

            submissions = submission_set.children.all()
            if not include_invisible:
                submissions = filter(lambda s: s.visible, submissions)
            submission_set.length = len(submissions)

            if submission_set.length == 0:
                continue

            serializer = SubmissionSetSummarySerializer(submission_set, context=self.context)
            serializer.parent = self
            summaries[submission_set.name] = serializer.data

        return summaries

    def get_detailed_submission_sets(self, place):
        """
        Get a mapping from place id to a detiled submission set dictionary.
        Get this for the entire dataset at once.
        """
        request = self.context['request']
        include_invisible = INCLUDE_INVISIBLE_PARAM in request.GET

        details = {}
        for submission_set in place.submission_sets.all():
            # Ensure the user has read permission on the submission set.
            user = getattr(request, 'user', None)
            client = getattr(request, 'client', None)
            dataset = getattr(request, 'get_dataset', lambda: None)()
            if not check_data_permission(user, client, 'retrieve', dataset, submission_set):
                continue

            submissions = submission_set.children.all()
            if not include_invisible:
                submissions = filter(lambda s: s.visible, submissions)

            if len(submissions) == 0:
                continue

            # We know that the submission datasets will be the same as the place
            # dataset, so say so and avoid an extra query for each.
            for submission in submissions:
                submission.dataset = place.dataset

            serializer = SubmissionSerializer(submissions, context=self.context, many=True)
            serializer.parent = self
            details[submission_set.name] = serializer.data

        return details

    def to_native(self, obj):
        obj = self.ensure_obj(obj)
        fields = self.get_fields()

        data = {
            'url': fields['url'].field_to_native(obj, 'pk'),  # = PlaceIdentityField()
            'id': obj.pk,  # = serializers.PrimaryKeyRelatedField(read_only=True)
            'geometry': str(obj.geometry or 'POINT(0 0)'),  # = GeometryField(format='wkt')
            'dataset': obj.dataset_id,  # = DataSetRelatedField()
            'attachments': [AttachmentSerializer(a).data for a in obj.attachments.all()],  # = AttachmentSerializer(read_only=True)
            'submitter': UserSerializer(obj.submitter).data if obj.submitter else None,
            'data': obj.data,
            'visible': obj.visible,
            'created_datetime': obj.created_datetime.isoformat() if obj.created_datetime else None,
            'updated_datetime': obj.updated_datetime.isoformat() if obj.updated_datetime else None,
        }

        data = self.explode_data_blob(data)

        # data = super(PlaceSerializer, self).to_native(obj)
        request = self.context['request']

        # TODO: Put this flag value directly in to the serializer context,
        #       instead of relying on the request query parameters.
        if INCLUDE_SUBMISSIONS_PARAM not in request.GET:
            submission_sets_getter = self.get_submission_set_summaries
        else:
            submission_sets_getter = self.get_detailed_submission_sets

        data['submission_sets'] = submission_sets_getter(obj)

        if hasattr(obj, 'distance'):
            data['distance'] = str(obj.distance)

        return data


class SubmissionSerializer (SubmittedThingSerializer, serializers.HyperlinkedModelSerializer):
    url = SubmissionIdentityField()
    id = serializers.PrimaryKeyRelatedField(read_only=True)
    dataset = DataSetRelatedField()
    set = SubmissionSetRelatedField(source='parent')
    place = PlaceRelatedField(source='parent.place')
    attachments = AttachmentSerializer(read_only=True, many=True)
    submitter = UserSerializer()

    class Meta:
        model = models.Submission
        exclude = ('parent',)


class AttachmentSerializer (EmptyModelSerializer, serializers.ModelSerializer):
    file = AttachmentFileField()

    class Meta:
        model = models.Attachment
        exclude = ('id', 'thing',)

    def to_native(self, obj):
        obj = self.ensure_obj(obj)
        return {
            'created_datetime': obj.created_datetime,
            'updated_datetime': obj.updated_datetime,
            'file': obj.file.storage.url(obj.file.name),
            'name': obj.name
        }


class DataSetSerializer (EmptyModelSerializer, serializers.HyperlinkedModelSerializer):
    url = DataSetIdentityField()
    id = serializers.PrimaryKeyRelatedField(read_only=True)
    owner = UserRelatedField()
    keys = DataSetKeysRelatedField(source='*', many=True)

    places = DataSetPlaceSetSummarySerializer(source='*', read_only=True, many=True)
    submission_sets = DataSetSubmissionSetSummarySerializer(source='*', read_only=True, many=True)

    class Meta:
        model = models.DataSet

    def to_native(self, obj):
        obj = self.ensure_obj(obj)
        fields = self.get_fields()
        fields['places'].context = self.context
        fields['submission_sets'].context = self.context

        data = {
            'url': fields['url'].field_to_native(obj, 'url'),
            'id': obj.pk,
            'slug': obj.slug,
            'display_name': obj.display_name,
            'owner': fields['owner'].field_to_native(obj, 'owner') if obj.owner_id else None,
            'keys': fields['keys'].field_to_native(obj, 'keys'),
            'places': fields['places'].field_to_native(obj, 'places'),
            'submission_sets': fields['submission_sets'].field_to_native(obj, 'submission_sets'),
        }

        return data


class ActionSerializer (EmptyModelSerializer, serializers.ModelSerializer):
    target_type = serializers.SerializerMethodField('get_target_type')
    target = serializers.SerializerMethodField('get_target')

    class Meta:
        model = models.Action
        exclude = ('thing', 'source')

    def get_target_type(self, obj):
        try:
            if obj.thing.place is not None:
                return u'place'
        except models.Place.DoesNotExist:
            pass

        return obj.thing.submission.parent.name

    def get_target(self, obj):
        try:
            if obj.thing.place is not None:
                serializer = PlaceSerializer(obj.thing.place)
            else:
                serializer = SubmissionSerializer(obj.thing.submission)
        except models.Place.DoesNotExist:
            serializer = SubmissionSerializer(obj.thing.submission)

        serializer.context = self.context
        return serializer.data


###############################################################################
#
# Pagination Serializers
# ----------------------
#

class PaginationMetadataSerializer (serializers.Serializer):
    length = serializers.Field(source='paginator.count')
    next = pagination.NextPageField(source='*')
    previous = pagination.PreviousPageField(source='*')
    page = serializers.Field(source='number')
    num_pages = serializers.Field(source='paginator.num_pages')


class PaginatedResultsSerializer (pagination.BasePaginationSerializer):
    metadata = PaginationMetadataSerializer(source='*')
    many = True


class FeatureCollectionSerializer (PaginatedResultsSerializer):
    results_field = 'features'

    def to_native(self, obj):
        data = super(FeatureCollectionSerializer, self).to_native(obj)
        data['type'] = 'FeatureCollection'
        return data

