"""
REST API Key model implementation derived from django-apikey,
copyright (c) 2011 Steve Scoursen and Jorge Eduardo Cardona.
BSD license.
http://pypi.python.org/pypi/django-apikey

Key generation derived from
http://jetfar.com/simple-api-key-generation-in-python/
license unknown.
"""

from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.timezone import now

# Changing this would require a migration, ugh.
KEY_SIZE = 32


class FakeDataSetManager (object):
    '''
    ApiKey <-> DataSet used to be a many-to-many relationship. It is now many-
    to-one, but for backwards compatibility we are keeping around the datasets
    member for now. This class is used to emulate a RelatedManager.
    '''
    def __init__(self, obj=None):
        self.obj = obj

    def all(self):
        return self

    def __iter__(self):
        return iter([self.obj.dataset])

    def __get__(self, instance, owner):
        self.obj = instance
        return self

class ApiKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='api_keys_v1')
    key = models.CharField(max_length=KEY_SIZE, unique=True)
    logged_ip = models.IPAddressField(blank=True, null=True)
    last_used = models.DateTimeField(blank=True, default=now)

    dataset = models.ForeignKey('sa_api_v1.DataSet', blank=True,
                                      related_name='api_keys')

    # A fake related manager for backwards compatibility
    datasets = FakeDataSetManager()

    class Meta:
        db_table = 'apikey_apikey'
        managed = False

    def login(self, ip_address):
        self.logged_ip = ip_address
        self.save()

    def logout(self):
        # YAGNI?
        self.logged_ip = None
        self.save()

    def __unicode__(self):
        return self.key


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
