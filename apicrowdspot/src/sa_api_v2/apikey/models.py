"""
REST API Key model implementation derived from django-apikey,
copyright (c) 2011 Steve Scoursen and Jorge Eduardo Cardona.
BSD license.
http://pypi.python.org/pypi/django-apikey

Key generation derived from
http://jetfar.com/simple-api-key-generation-in-python/
license unknown.
"""

from django.db import models
from django.db.models.signals import post_save
from django.utils.timezone import now
from ..models import DataSet, KeyPermission
from .. import utils

# Changing this would require a migration, ugh.
KEY_SIZE = 32


def generate_unique_api_key():
    """random string suitable for use with ApiKey.

    Algorithm from http://jetfar.com/simple-api-key-generation-in-python/
    """
    import base64
    import hashlib
    import random
    api_key = ''
    while len(api_key) < KEY_SIZE:
        more_key = str(random.getrandbits(256))
        more_key = hashlib.sha256(more_key).hexdigest()
        more_key = base64.b64encode(
            more_key,
            random.choice(['rA', 'aZ', 'gQ', 'hH', 'hG', 'aR', 'DD']))
        more_key = more_key.rstrip('=')
        api_key += more_key
    api_key = api_key[:KEY_SIZE]
    return api_key


class ApiKey(models.Model):
    key = models.CharField(max_length=KEY_SIZE, unique=True, default=generate_unique_api_key)
    logged_ip = models.IPAddressField(blank=True, null=True)
    last_used = models.DateTimeField(blank=True, default=now)
    dataset = models.ForeignKey(DataSet, blank=True, related_name='keys')

    class Meta:
        db_table = 'apikey_apikey'

    def login(self, ip_address):
        self.logged_ip = ip_address
        self.save()

    def logout(self):
        # YAGNI?
        self.logged_ip = None
        self.save()

    @property
    def owner(self):
        try:
            return self.dataset.owner
        except AttributeError:
            return None

    def __unicode__(self):
        return self.key

    @utils.memo
    def get_permissions(self):
        return self.permissions

    def save(self, *args, **kwargs):
        if self.logged_ip == '':
            self.logged_ip = None
        return super(ApiKey, self).save(*args, **kwargs)


def create_data_permissions(sender, instance, created, **kwargs):
    """
    Create a default permission instance for a new API key.
    """
    if created:
        KeyPermission.objects.create(key=instance, submission_set='*',
            can_retrieve=True, can_create=True, can_update=True, can_destroy=True)
post_save.connect(create_data_permissions, sender=ApiKey, dispatch_uid="apikey-create-permissions")
