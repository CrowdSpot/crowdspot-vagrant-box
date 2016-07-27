from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from django.http import HttpResponseRedirect

admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'project.views.home', name='home'),
    # url(r'^project/', include('project.foo.urls')),

    # NOTE: Redirect all manager urls until the manager is fixed.
    url(r'^$', lambda x: HttpResponseRedirect('http://openplans.org/shareabouts/')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),

    # Django REST framework needs its namespace declared in order to render
    # the browsable API pages.
    url(r'^restframework', include('djangorestframework.urls', namespace='djangorestframework')),

    # For now, use basic auth.
    url(r'^accounts/', include('django.contrib.auth.urls')),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout_then_login',
        name='manager_logout'),

    # For now, the API and the management console are hosted together.
    url(r'^api/v2/', include('sa_api_v2.urls')),
    url(r'^api/v1/', include('sa_api_v1.urls', namespace='v1')),
    # NOTE: Redirect all manager urls until the manager is fixed.
    url(r'^manage/', lambda x: HttpResponseRedirect('http://openplans.org/shareabouts/')),

)
