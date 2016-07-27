from django.contrib.auth import get_user_model
from django.test import TestCase
import mock
from nose.tools import istest
from nose.tools import assert_equal, assert_in, assert_not_in, ok_

from ..resources import ModelResourceWithDataBlob
from ..models import SubmittedThing, DataSet


User = get_user_model()

def make_model_mock(model, **kw):
    spec = [attr for attr in dir(model) if not attr.endswith('__')]
    spec += kw.keys()
    from mock_django.models import _ModelMock
    mock = _ModelMock(model, spec)
    for k, v in kw.items():
        setattr(mock, k, v)
    return mock


class TestFunctions(object):

    @istest
    def simple_user(self):
        class MockUser(object):
            pk = 1
            username = 'bob'
            anything_else = 'ignored'

        from ..resources import simple_user
        assert_equal(simple_user(MockUser()),
                     {'id': 1, 'username': 'bob'})


class TestModelResourceWithDataBlob(object):
    def setUp(self):
        User.objects.all().delete()
        DataSet.objects.all().delete()
        SubmittedThing.objects.all().delete()

    def _get_resource_and_instance(self):
        resource = ModelResourceWithDataBlob()
        resource.model = SubmittedThing

        user = User.objects.create_user(username='paul')
        dataset_instance = DataSet.objects.create(owner=user, slug='ds')
        submitted_thing = SubmittedThing.objects.create(dataset=dataset_instance)
        # Need an instance to avoid auto-creating one.
        resource.view = mock.Mock(flags={})
        resource.view.model_instance = submitted_thing
        # ... and it needs some other attributes to avoid making a
        # useless mock form.
        resource.view.form = None
        resource.view.method = None
        return resource, submitted_thing

    @istest
    def serialize_with_data_blob(self):
        resource, submitted_thing = self._get_resource_and_instance()

        submitted_thing.data = '{"animals": ["dogs", "cats"]}'
        submitted_thing.submitter_name = 'Jacques Tati'
        result = resource.serialize(submitted_thing)

        assert_equal(result['animals'], ['dogs', 'cats'])
        assert_not_in('data', result)
        ok_(result['visible'])
        assert_equal(result['dataset']['id'], submitted_thing.dataset.id)

    @istest
    def serialize_with_private_data(self):
        resource, submitted_thing = self._get_resource_and_instance()

        submitted_thing.data = '{"animals": ["dogs", "cats"], "private-email": "admin@example.com"}'
        submitted_thing.submitter_name = 'Jacques Tati'
        result = resource.serialize(submitted_thing)

        assert_equal(result['animals'], ['dogs', 'cats'])
        assert_not_in('data', result)
        assert_not_in('private-email', result)
        ok_(result['visible'])
        assert_equal(result['dataset']['id'], submitted_thing.dataset.id)

    @istest
    def serialize_with_private_data_and_permission(self):
        resource, submitted_thing = self._get_resource_and_instance()
        resource.view.flags['include_private_data'] = True

        submitted_thing.data = '{"animals": ["dogs", "cats"], "private-email": "admin@example.com"}'
        submitted_thing.submitter_name = 'Jacques Tati'
        result = resource.serialize(submitted_thing)

        assert_equal(result['animals'], ['dogs', 'cats'])
        assert_not_in('data', result)
        assert_in('private-email', result)
        ok_(result['visible'])
        assert_equal(result['dataset']['id'], submitted_thing.dataset.id)

    @istest
    def serialize_list_with_private_data(self):
        resource, submitted_thing = self._get_resource_and_instance()

        submitted_thing.data = '{"animals": ["dogs", "cats"], "private-email": "admin@example.com"}'
        submitted_thing.submitter_name = 'Jacques Tati'
        result = resource.serialize([submitted_thing, submitted_thing])

        assert_equal(len(result), 2)
        assert_equal(result[0]['animals'], ['dogs', 'cats'])
        assert_not_in('data', result[0])
        assert_not_in('private-email', result[0])
        ok_(result[0]['visible'])
        assert_equal(result[0]['dataset']['id'], submitted_thing.dataset.id)

    @istest
    def serialize_list_with_private_data_and_permission(self):
        resource, submitted_thing = self._get_resource_and_instance()
        resource.view.flags['include_private_data'] = True

        submitted_thing.data = '{"animals": ["dogs", "cats"], "private-email": "admin@example.com"}'
        submitted_thing.submitter_name = 'Jacques Tati'
        result = resource.serialize([submitted_thing, submitted_thing])

        assert_equal(len(result), 2)
        assert_equal(result[0]['animals'], ['dogs', 'cats'])
        assert_not_in('data', result[0])
        assert_in('private-email', result[0])
        ok_(result[0]['visible'])
        assert_equal(result[0]['dataset']['id'], submitted_thing.dataset.id)

    @istest
    def validate_request_with_origdata(self):
        resource, submitted_thing = self._get_resource_and_instance()

        result = resource.validate_request({'submitter_name': 'ralphie',
                                            'x': 'xylophone',
                                            'dataset': submitted_thing.dataset.id,
                                            'visible': True})

        # Anything not in the model's fields gets converted to the 'data'
        # JSON blog.
        assert_equal(
            result,
            {'dataset': submitted_thing.dataset,
             'data': u'{"x":"xylophone","submitter_name":"ralphie"}', 'visible': True}
        )


class TestPlaceResource(TestCase):

    def _cleanup(self):
        from sa_api_v1 import models
        from django.core.cache import cache
        models.Submission.objects.all().delete()
        models.SubmissionSet.objects.all().delete()
        models.Place.objects.all().delete()
        models.DataSet.objects.all().delete()
        User.objects.all().delete()
        cache.clear()

    def setUp(self):
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def populate(self):
        from ..resources import models
        location = 'POINT (1.0 2.0)'
        owner = User.objects.create(username='user')
        ds = models.DataSet.objects.create(owner=owner, slug='dataset')

        models.Place.objects.create(id=123, location=location, dataset_id=ds.id)
        models.Place.objects.create(id=456, location=location, dataset_id=ds.id)
        # A couple of SubmissionSets: one with 3 children, one with 2.
        ss1 = models.SubmissionSet.objects.create(place_id=123,
                                                  submission_type='foo')  # count=3

        for i in range(3):
            models.Submission.objects.create(parent=ss1, dataset_id=ds.id)

        ss2 = models.SubmissionSet.objects.create(place_id=456,
                                                  submission_type='bar')
        for i in range(2):
            models.Submission.objects.create(parent=ss2, dataset_id=ds.id)

        self.ds = ds

    @istest
    def submission_sets_empty(self):
        from ..resources import models, PlaceResource, SubmissionSetResource
        from mock_django.managers import ManagerMock
        mock_manager = ManagerMock(models.SubmissionSet.objects)
        with mock.patch.object(models.SubmissionSet, 'objects', mock_manager):
            submission_set_func = SubmissionSetResource().serialize_by_dataset
            assert_equal(PlaceResource().model.cache.get_submission_sets(0, submission_set_func), {})

    @istest
    def submission_sets_non_empty(self):
        from ..resources import models, PlaceResource, SubmissionSetResource
        self.populate()
        expected_result = {
            123: [{'length': 3, 'url': '/api/v1/user/datasets/dataset/places/123/foo/', 'type': 'foo'}],
            456: [{'length': 2, 'url': '/api/v1/user/datasets/dataset/places/456/bar/', 'type': 'bar'}],
        }
        submission_set_func = SubmissionSetResource().serialize_by_dataset
        assert_equal(dict(PlaceResource().model.cache.get_submission_sets(
            self.ds.id, submission_set_func)), expected_result)
        for place in models.Place.objects.all():
            assert_in(place.id, expected_result)

    @istest
    def test_location(self):
        from ..resources import PlaceResource
        place = mock.Mock()
        place.location.x = 123
        place.location.y = 456
        assert_equal(PlaceResource().location(place),
                     {'lng': 123, 'lat': 456})

    @istest
    def test_validate_request(self):
        from ..resources import PlaceResource, ModelResourceWithDataBlob
        resource = PlaceResource()
        with mock.patch.object(ModelResourceWithDataBlob, 'validate_request') as patched_super_validate:
            # To avoid needing to wire up ModelResourceWithDataBlob
            # for this test, we have its super_validate just return its args
            # unchanged.
            patched_super_validate.side_effect = lambda *args: args

            data, files = resource.validate_request({'location': {'lat': 1, 'lng': 2}})
            assert_equal(data, {'location': 'POINT (2 1)'})

            data, files = resource.validate_request({})
            assert_equal(data, {})

    @istest
    def test_url(self):
        self.populate()
        from ..resources import models, PlaceResource
        # White-box test - we hook up the stuff we know it uses.
        resource = PlaceResource()
        user = User.objects.create(username='test-user')
        dataset = models.DataSet.objects.create(id=456, slug='test-set',
                                                owner=user)

        place = models.Place.objects.create(id=124, dataset=dataset, location='POINT(1 1)')
        # TODO: call reverse() here to avoid breaking if using a different urls.py?
        assert_equal(resource.url(place),
                     '/api/v1/test-user/datasets/test-set/places/124/')
        # Called twice to get coverage of memoization.
        assert_equal(resource.url(place),
                     '/api/v1/test-user/datasets/test-set/places/124/')

        # Call with different place, to make sure the cache is behaving.
        place = models.Place.objects.create(id=125, dataset=dataset, location='POINT(1 1)')
        assert_equal(resource.url(place),
                     '/api/v1/test-user/datasets/test-set/places/125/')

    @istest
    def serialize_with_submission_data(self):
        from ..models import DataSet, Place, SubmissionSet, Submission
        user = User.objects.create(username='user')
        ds = DataSet.objects.create(owner=user, slug='ds')
        place = Place.objects.create(location='POINT(0 0)', dataset=ds)
        ss = SubmissionSet.objects.create(place=place, submission_type='set')
        Submission.objects.create(parent=ss, dataset=ds, data='{"val": 1}')
        Submission.objects.create(parent=ss, dataset=ds, data='{"val": 2}')

        from ..resources import PlaceResource
        resource = PlaceResource()
        resource.view = mock.Mock(flags={'include_submissions': True})

        data = resource.serialize(place)
        submission_set = data['submissions'][0]
        assert_equal(type(submission_set), list)
        assert_equal(len(submission_set), 2)
        assert_equal(set([s['val'] for s in submission_set]), set([1, 2]))


class TestDataSetResource(object):

    @istest
    def test_owner(self):
        from ..resources import DataSetResource
        resource = DataSetResource()
        dataset = mock.Mock()
        dataset.owner.pk = 123
        dataset.owner.username = 'freddy'
        assert_equal(resource.owner(dataset), {'id': 123, 'username': 'freddy'})

    @istest
    def test_places(self):
        from ..resources import DataSetResource
        from mock_django.managers import ManagerMock
        from ..models import Place
        place1 = mock.Mock()
        place1.id = 123
        place2 = mock.Mock()
        place2.id = 456
        place_mgr = ManagerMock(Place.objects, place1, place2)
        place_mgr.values.annotate = mock.Mock(return_value=[{'dataset_id': 1,
                                                             'length': 2}])

        with mock.patch.object(Place, 'objects', place_mgr):
            resource = DataSetResource()
            dataset = mock.Mock()
            dataset.owner.username = 'mock-user'
            dataset.slug = 'mock-dataset'
            dataset.id = 1
            assert_equal(resource.places(dataset),
                         {'url': '/api/v1/mock-user/datasets/mock-dataset/places/',
                          'length': 2})


class TestActivityResource(object):

    @istest
    def test_things(self):
        from ..resources import ActivityResource
        p1 = mock.Mock(submittedthing_ptr_id=1, id=10)
        p2 = mock.Mock(submittedthing_ptr_id=2, id=20)
        mock_places = [p1, p2]

        s1 = mock.Mock(submittedthing_ptr_id=30, id=300)
        s1.parent.submission_type = 'stype1'
        s1.parent.place_id = 300
        s2 = mock.Mock(submittedthing_ptr_id=40)
        s2.parent.submission_type = 'stype2'
        s2.parent.place_id = 400
        mock_submissions = [s1, s2]

        mock_view = mock.Mock()
        mock_view.get_places = mock.Mock(return_value=mock_places)
        mock_view.get_submissions = mock.Mock(return_value=mock_submissions)

        resource = ActivityResource(view=mock_view)

        assert_equal(
            resource.things,
            {
                1: {'data': p1, 'place_id': 10, 'type': 'places'},
                2: {'data': p2, 'place_id': 20, 'type': 'places'},
                30: {'data': s1, 'place_id': 300, 'type': 'stype1'},
                40: {'data': s2, 'place_id': 400, 'type': 'stype2'},
            }
        )
