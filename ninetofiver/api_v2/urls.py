"""925r API v2 URLs."""
from django.conf.urls import include, url
from rest_framework import routers
from django_downloadview import ObjectDownloadView
from ninetofiver.api_v2 import views
from ninetofiver import models

urlpatterns = [
    # url(r'^api/$', views.schema_view, name='api_docs'),
]

router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'leave_types', views.LeaveTypeViewSet)
router.register(r'contract_roles', views.ContractRoleViewSet)
router.register(r'performance_types', views.PerformanceTypeViewSet)
router.register(r'locations', views.LocationViewSet)
router.register(r'holidays', views.HolidayViewSet)
router.register(r'timesheets', views.TimesheetViewSet)
router.register(r'leave', views.LeaveViewSet)
router.register(r'contracts', views.ContractViewSet)
router.register(r'contract_users', views.ContractUserViewSet)
router.register(r'whereabouts', views.WhereaboutViewSet)
router.register(r'performances', views.PerformanceViewSet)
router.register(r'attachments', views.AttachmentViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browseable API.
urlpatterns += [
    url(r'^', include(router.urls + [
        url(r'^me/$', views.MeAPIView.as_view()),
        url(r'^feeds/leave/all.ics$', views.LeaveFeedAPIView.as_view()),
        url(r'^feeds/leave/me.ics$', views.UserLeaveFeedAPIView.as_view()),
        url(r'^feeds/leave/(?P<user_username>[A-Za-z0-9_-]+).ics$', views.UserLeaveFeedAPIView.as_view()),
        url(r'^feeds/whereabouts/all.ics$', views.WhereaboutFeedAPIView.as_view()),
        url(r'^feeds/whereabouts/me.ics$', views.UserWhereaboutFeedAPIView.as_view()),
        url(r'^feeds/whereabouts/(?P<user_username>[A-Za-z0-9_-]+).ics$', views.UserWhereaboutFeedAPIView.as_view()),

        url(r'^downloads/attachments/(?P<slug>[A-Za-z0-9_-]+)/$', ObjectDownloadView.as_view(model=models.Attachment, file_field='file'), name='download_attachment'),
        url(r'^downloads/company_logos/(?P<pk>[0-9]+)/$', ObjectDownloadView.as_view(model=models.Company, file_field='logo', attachment=False), name='download_company_logo'),
        url(r'^downloads/timesheet_contract_pdf/(?P<timesheet_pk>[0-9]+)/(?P<contract_pk>[0-9]+)/$', views.TimesheetContractPdfDownloadAPIView.as_view(), name='download_timesheet_contract_pdf'),

        url(r'^imports/performances/$', views.PerformanceImportAPIView.as_view()),
        url(r'^range_info/$', views.RangeInfoAPIView.as_view()),
        url(r'^range_availability/$', views.RangeAvailabilityAPIView.as_view()),

        # url(r'^services/my_user/$', views.MyUserServiceAPIView.as_view(), name='my_user_service'),
        # url(r'^services/leave_request/$', views.LeaveRequestServiceAPIView.as_view(), name='leave_request_service'),
        # url(r'^services/performance_import/$', views.PerformanceImportServiceAPIView.as_view(), name='performance_import_service'),
        # url(r'^services/range_availability/$', views.RangeAvailabilityServiceAPIView.as_view(), name='range_availability_service'),
        # url(r'^services/range_info/$', views.RangeInfoServiceAPIView.as_view(), name='range_info_service'),
        # url(r'^services/download_attachment/(?P<slug>[A-Za-z0-9_-]+)/$', ObjectDownloadView.as_view(model=models.Attachment, file_field='file'), name='download_attachment_service'),
        # url(r'^services/download_company_logo/(?P<pk>[0-9]+)/$', ObjectDownloadView.as_view(model=models.Company, file_field='logo', attachment=False), name='download_company_logo_service'),
        # url(r'^services/my_timesheet_contract_pdf_export/(?P<timesheet_pk>[0-9]+)/(?P<contract_pk>[0-9_-]+)/$', views.MyTimesheetContractPdfExportServiceAPIView.as_view(), name='my_timesheet_contract_pdf_export_service'),
        # url(r'^services/feeds/leave/user/(?P<user_username>[A-Za-z0-9_-]+)\.ics$', views.UserLeaveFeedServiceAPIView.as_view()),
        # url(r'^services/feeds/leave/me\.ics$', views.UserLeaveFeedServiceAPIView.as_view()),
        # url(r'^services/feeds/leave\.ics$', views.LeaveFeedServiceAPIView.as_view()),
        # url(r'^services/feeds/whereabouts/user/(?P<user_username>[A-Za-z0-9_-]+)\.ics$', views.UserWhereaboutFeedServiceAPIView.as_view()),
        # url(r'^services/feeds/whereabouts/me\.ics$', views.UserWhereaboutFeedServiceAPIView.as_view()),
        # url(r'^services/feeds/whereabouts\.ics$', views.WhereaboutFeedServiceAPIView.as_view()),
    ])),
]