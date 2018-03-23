from django.contrib.auth import models as auth_models
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from ninetofiver import filters
from ninetofiver import models
from ninetofiver import serializers
from ninetofiver import redmine
from ninetofiver import feeds
from ninetofiver.viewsets import GenericHierarchicalReadOnlyViewSet
from rest_framework import parsers
from rest_framework import permissions
from rest_framework import response
from rest_framework import status
from rest_framework import schemas
from rest_framework import viewsets
from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.decorators import renderer_classes
from rest_framework.renderers import CoreJSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_swagger.renderers import OpenAPIRenderer
from rest_framework_swagger.renderers import SwaggerUIRenderer
from ninetofiver import settings, tables, calculation, pagination
from ninetofiver.utils import month_date_range
from django.db.models import Q
from django_tables2 import RequestConfig
from django_tables2.export.export import TableExport
from datetime import datetime, date, timedelta
from wkhtmltopdf.views import PDFTemplateView
from dateutil import parser
import logging
import copy


logger = logging.getLogger(__name__)


# Reused classes

class BaseTimesheetContractPdfExportServiceAPIView(PDFTemplateView, generics.GenericAPIView):
    """Export a timesheet contract to PDF."""

    filename = 'timesheet_contract.pdf'
    template_name = 'ninetofiver/timesheets/timesheet_contract_pdf_export.pug'

    def resolve_user(self, context):
        """Resolve the user for this export."""
        raise NotImplementedError()

    def render_to_response(self, context, **response_kwargs):
        user = self.resolve_user(context)
        timesheet = get_object_or_404(models.Timesheet, pk=context.get('timesheet_pk', None), user=user)
        contract = get_object_or_404(models.Contract, pk=context.get('contract_pk', None), contractuser__user=user)

        context['user'] = user
        context['timesheet'] = timesheet
        context['contract'] = contract
        context['performances'] = (models.ActivityPerformance.objects
                                   .filter(timesheet=timesheet, contract=contract)
                                   .order_by('day')
                                   .all())
        context['total_performed_hours'] = sum([x.duration for x in context['performances']])
        context['total_performed_days'] = round(context['total_performed_hours'] / 8, 2)

        return super().render_to_response(context, **response_kwargs)


# Homepage and others
def home_view(request):
    """Homepage."""
    context = {}
    return render(request, 'ninetofiver/home/index.pug', context)


@login_required
def account_view(request):
    """User-specific account page."""
    context = {}
    return render(request, 'ninetofiver/account/index.pug', context)


@api_view(exclude_from_schema=True)
@renderer_classes([OpenAPIRenderer, SwaggerUIRenderer, CoreJSONRenderer])
@permission_classes((permissions.IsAuthenticated,))
def schema_view(request):
    """API documentation."""
    generator = schemas.SchemaGenerator(title='Ninetofiver API')
    return response.Response(generator.get_schema(request=request))


# Admin-only
@staff_member_required
def admin_leave_approve_view(request, leave_pk):
    """Approve the selected leaves."""
    leave_pks = list(map(int, leave_pk.split(',')))
    return_to_referer = request.GET.get('return', 'false').lower() == 'true'

    leaves = models.Leave.objects.filter(id__in=leave_pks, status=models.STATUS_PENDING)

    for leave in leaves:
        leave.status = models.STATUS_APPROVED
        leave.save()

    context = {
        'leaves': leaves,
    }

    if return_to_referer and request.META.get('HTTP_REFERER', None):
        return redirect(request.META.get('HTTP_REFERER'))

    return render(request, 'ninetofiver/admin/leaves/approve.pug', context)


@staff_member_required
def admin_leave_reject_view(request, leave_pk):
    """Reject the selected leaves."""
    leave_pks = list(map(int, leave_pk.split(',')))
    return_to_referer = request.GET.get('return', 'false').lower() == 'true'

    leaves = models.Leave.objects.filter(id__in=leave_pks, status=models.STATUS_PENDING)

    for leave in leaves:
        leave.status = models.STATUS_REJECTED
        leave.save()

    context = {
        'leaves': leaves,
    }

    if return_to_referer and request.META.get('HTTP_REFERER', None):
        return redirect(request.META.get('HTTP_REFERER'))

    return render(request, 'ninetofiver/admin/leaves/reject.pug', context)


@staff_member_required
def admin_timesheet_close_view(request, timesheet_pk):
    """Close the selected timesheets."""
    timesheet_pks = list(map(int, timesheet_pk.split(',')))
    return_to_referer = request.GET.get('return', 'false').lower() == 'true'

    timesheets = models.Timesheet.objects.filter(id__in=timesheet_pks, status=models.STATUS_PENDING)

    for timesheet in timesheets:
        timesheet.status = models.STATUS_CLOSED
        timesheet.save()

    context = {
        'timesheets': timesheets,
    }

    if return_to_referer and request.META.get('HTTP_REFERER', None):
        return redirect(request.META.get('HTTP_REFERER'))

    return render(request, 'ninetofiver/admin/timesheets/close.pug', context)


@staff_member_required
def admin_timesheet_activate_view(request, timesheet_pk):
    """Activate the selected timesheets."""
    timesheet_pks = list(map(int, timesheet_pk.split(',')))
    return_to_referer = request.GET.get('return', 'false').lower() == 'true'

    timesheets = models.Timesheet.objects.filter(id__in=timesheet_pks, status=models.STATUS_PENDING)

    for timesheet in timesheets:
        timesheet.status = models.STATUS_ACTIVE
        timesheet.save()

    context = {
        'timesheets': timesheets,
    }

    if return_to_referer and request.META.get('HTTP_REFERER', None):
        return redirect(request.META.get('HTTP_REFERER'))

    return render(request, 'ninetofiver/admin/timesheets/activate.pug', context)


@staff_member_required
def admin_report_index_view(request):
    """Report index."""
    context = {
        'title': _('Reports'),
    }

    return render(request, 'ninetofiver/admin/reports/index.pug', context)


@staff_member_required
def admin_report_timesheet_contract_overview_view(request):
    """Timesheet contract overview report."""
    fltr = filters.AdminReportTimesheetContractOverviewFilter(request.GET, models.Timesheet.objects)
    timesheets = fltr.qs.select_related('user')
    try:
        contract = int(request.GET.get('performance__contract', None))
    except Exception:
        contract = None

    data = []
    for timesheet in timesheets:
        date_range = timesheet.get_date_range()
        range_info = calculation.get_range_info([timesheet.user], date_range[0], date_range[1], summary=True)

        for contract_performance in range_info[timesheet.user.id]['summary']['performances']:
            if (not contract) or (contract == contract_performance['contract'].id):
                data.append({
                    'contract': contract_performance['contract'],
                    'duration': contract_performance['duration'],
                    'timesheet': timesheet,
                })

    config = RequestConfig(request, paginate={'per_page': pagination.CustomizablePageNumberPagination.page_size})
    table = tables.TimesheetContractOverviewTable(data)
    config.configure(table)

    export_format = request.GET.get('_export', None)
    if TableExport.is_valid_format(export_format):
        exporter = TableExport(export_format, table)
        return exporter.response('table.{}'.format(export_format))

    context = {
        'title': _('Timesheet contract overview'),
        'table': table,
        'filter': fltr,
    }

    return render(request, 'ninetofiver/admin/reports/timesheet_contract_overview.pug', context)


@staff_member_required
def admin_report_timesheet_overview_view(request):
    """Timesheet overview report."""
    fltr = filters.AdminReportTimesheetOverviewFilter(request.GET, models.Timesheet.objects)
    timesheets = fltr.qs.select_related('user')

    data = []
    for timesheet in timesheets:
        date_range = timesheet.get_date_range()
        range_info = calculation.get_range_info([timesheet.user], date_range[0], date_range[1])
        range_info = range_info[timesheet.user.id]

        data.append({
            'timesheet': timesheet,
            'range_info': range_info,
        })

    config = RequestConfig(request, paginate={'per_page': pagination.CustomizablePageNumberPagination.page_size})
    table = tables.TimesheetOverviewTable(data)
    config.configure(table)

    export_format = request.GET.get('_export', None)
    if TableExport.is_valid_format(export_format):
        exporter = TableExport(export_format, table)
        return exporter.response('table.{}'.format(export_format))

    context = {
        'title': _('Timesheet overview'),
        'table': table,
        'filter': fltr,
    }

    return render(request, 'ninetofiver/admin/reports/timesheet_overview.pug', context)


@staff_member_required
def admin_report_user_range_info_view(request):
    """User range info report."""
    fltr = filters.AdminReportUserRangeInfoFilter(request.GET, models.Timesheet.objects.all())
    user = get_object_or_404(auth_models.User.objects,
                             pk=request.GET.get('user', None), is_active=True) if request.GET.get('user') else None
    from_date = parser.parse(request.GET.get('from_date', None)).date() if request.GET.get('from_date') else None
    until_date = parser.parse(request.GET.get('until_date', None)).date() if request.GET.get('until_date') else None

    data = []

    if user and from_date and until_date and (until_date >= from_date):
        range_info = calculation.get_range_info([user], from_date, until_date, daily=True)[user.id]

        for day in sorted(range_info['details'].keys()):
            day_detail = range_info['details'][day]
            data.append({
                'day_detail': day_detail,
                'date': parser.parse(day),
                'user': user,
            })

    config = RequestConfig(request, paginate={'per_page': pagination.CustomizablePageNumberPagination.page_size * 2})
    table = tables.UserRangeInfoTable(data)
    config.configure(table)

    export_format = request.GET.get('_export', None)
    if TableExport.is_valid_format(export_format):
        exporter = TableExport(export_format, table)
        return exporter.response('table.{}'.format(export_format))

    context = {
        'title': _('User range info'),
        'table': table,
        'filter': fltr,
    }

    return render(request, 'ninetofiver/admin/reports/user_range_info.pug', context)


@staff_member_required
def admin_report_user_leave_overview_view(request):
    """User leave overview report."""
    fltr = filters.AdminReportUserLeaveOverviewFilter(request.GET, models.LeaveDate.objects.all())
    data = []

    if fltr.data.get('user', None) and fltr.data.get('year', None):
        year = int(fltr.data['year'])

        # Grab leave types, index them by ID
        leave_types = models.LeaveType.objects.all()

        # Grab leave dates, index them by year, then month, then leave type ID
        leave_dates = fltr.qs.select_related('leave', 'leave__leave_type')
        leave_date_data = {}
        for leave_date in leave_dates:
            (leave_date_data
                .setdefault(leave_date.starts_at.year, {})
                .setdefault(leave_date.starts_at.month, {})
                .setdefault(leave_date.leave.leave_type.id, [])
                .append(leave_date))

        # Iterate over years, months to create monthly data
        for month in range(1, 1 + 12):
            month_leave_dates = leave_date_data.get(year, {}).get(month, {})
            month_leave_type_hours = {}

            # Iterate over leave types to gather totals
            for leave_type in leave_types:
                duration = sum([Decimal(str(round((x.ends_at - x.starts_at).total_seconds() / 3600, 2)))
                                for x in month_leave_dates.get(leave_type.id, [])])
                month_leave_type_hours[leave_type.name] = duration

            data.append({
                'year': year,
                'month': month,
                'leave_type_hours': month_leave_type_hours,
            })

    config = RequestConfig(request, paginate={'per_page': pagination.CustomizablePageNumberPagination.page_size})
    table = tables.UserLeaveOverviewTable(data)
    config.configure(table)

    export_format = request.GET.get('_export', None)
    if TableExport.is_valid_format(export_format):
        exporter = TableExport(export_format, table)
        return exporter.response('table.{}'.format(export_format))

    context = {
        'title': _('User leave overview'),
        'table': table,
        'filter': fltr,
    }

    return render(request, 'ninetofiver/admin/reports/user_leave_overview.pug', context)


class AdminTimesheetContractPdfExportView(BaseTimesheetContractPdfExportServiceAPIView):
    """Export a timesheet contract to PDF."""

    permission_classes = (permissions.IsAdminUser,)

    def resolve_user(self, context):
        return get_object_or_404(auth_models.User, pk=context.get('user_pk', None))


# API calls
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows users to be viewed."""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = serializers.UserSerializer
    filter_class = filters.UserFilter
    queryset = (auth_models.User.objects.distinct().exclude(is_active=False).order_by('-date_joined')
                .select_related('userinfo').prefetch_related('groups'))


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows groups to be viewed."""

    queryset = auth_models.Group.objects.all()
    serializer_class = serializers.GroupSerializer
    permission_classes = (permissions.IsAuthenticated,)


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows companies to be viewed."""

    queryset = models.Company.objects.all()
    serializer_class = serializers.CompanySerializer
    filter_class = filters.CompanyFilter
    permission_classes = (permissions.IsAuthenticated,)


class EmploymentContractTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows employment contract types to be viewed."""

    queryset = models.EmploymentContractType.objects.all()
    serializer_class = serializers.EmploymentContractTypeSerializer
    filter_class = filters.EmploymentContractTypeFilter
    permission_classes = (permissions.IsAuthenticated,)


class UserRelativeViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows user relatives to be viewed."""

    queryset = models.UserRelative.objects.all()
    serializer_class = serializers.UserRelativeSerializer
    filter_class = filters.UserRelativeFilter
    permission_classes = (permissions.IsAuthenticated,)


class HolidayViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows holidays to be viewed."""

    queryset = models.Holiday.objects.all()
    serializer_class = serializers.HolidaySerializer
    filter_class = filters.HolidayFilter
    permission_classes = (permissions.IsAuthenticated,)


class LeaveTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows leave types to be viewed."""

    queryset = models.LeaveType.objects.all()
    serializer_class = serializers.LeaveTypeSerializer
    filter_class = filters.LeaveTypeFilter
    permission_classes = (permissions.IsAuthenticated,)


class LeaveViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows leaves to be viewed."""

    queryset = models.Leave.objects.all()
    serializer_class = serializers.LeaveSerializer
    filter_class = filters.LeaveFilter
    permission_classes = (permissions.IsAuthenticated,)


class LeaveDateViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows leave dates to be viewed."""

    queryset = models.LeaveDate.objects.all()
    serializer_class = serializers.LeaveDateSerializer
    filter_class = filters.LeaveDateFilter
    permission_classes = (permissions.IsAuthenticated,)


class PerformanceTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows performance types to be viewed."""

    queryset = models.PerformanceType.objects.all()
    serializer_class = serializers.PerformanceTypeSerializer
    filter_class = filters.PerformanceTypeFilter
    permission_classes = (permissions.IsAuthenticated,)


class TimesheetViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows timesheets to be viewed."""

    queryset = models.Timesheet.objects.all()
    serializer_class = serializers.TimesheetSerializer
    filter_class = filters.TimesheetFilter
    permission_classes = (permissions.DjangoModelPermissions,)


class AttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows attachments to be viewed."""

    queryset = models.Attachment.objects.all()
    serializer_class = serializers.AttachmentSerializer
    filter_class = filters.AttachmentFilter
    permission_classes = (permissions.DjangoModelPermissions,)


class PerformanceViewSet(GenericHierarchicalReadOnlyViewSet):
    """API endpoint that allows performance to be viewed."""

    queryset = models.Performance.objects.all()
    serializer_class = serializers.PerformanceSerializer
    serializer_classes = {
        models.ActivityPerformance: serializers.ActivityPerformanceSerializer,
        models.StandbyPerformance: serializers.StandbyPerformanceSerializer,
    }
    filter_class = filters.PerformanceFilter
    permission_classes = (permissions.DjangoModelPermissions,)


class ActivityPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows activity performance to be viewed."""

    queryset = models.ActivityPerformance.objects.all()
    filter_class = filters.ActivityPerformanceFilter
    permission_classes = (permissions.DjangoModelPermissions,)
    serializer_class = serializers.ActivityPerformanceSerializer


class StandbyPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows consultancy standby performance to be viewed or edited."""

    queryset = models.StandbyPerformance.objects.all()
    filter_class = filters.StandbyPerformanceFilter
    permission_classes = (permissions.DjangoModelPermissions,)
    serializer_class = serializers.StandbyPerformanceSerializer


class EmploymentContractViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows employment contracts to be viewed."""

    queryset = models.EmploymentContract.objects.all()
    filter_class = filters.EmploymentContractFilter
    permission_classes = (permissions.DjangoModelPermissions,)
    serializer_class = serializers.EmploymentContractSerializer


class WorkScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows work schedules to be viewed."""

    queryset = models.WorkSchedule.objects.all()
    filter_class = filters.WorkScheduleFilter
    permission_classes = (permissions.DjangoModelPermissions,)
    serializer_class = serializers.WorkScheduleSerializer


class ContractViewSet(GenericHierarchicalReadOnlyViewSet):
    """API endpoint that allows contracts to be viewed."""

    queryset = models.Contract.objects.all()
    serializer_class = serializers.ContractSerializer
    serializer_classes = {
        models.ProjectContract: serializers.ProjectContractSerializer,
        models.ConsultancyContract: serializers.ConsultancyContractSerializer,
        models.SupportContract: serializers.SupportContractSerializer,
    }
    filter_class = filters.ContractFilter
    permission_classes = (permissions.DjangoModelPermissions,)


class ProjectContractViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows project contracts to be viewed."""

    queryset = models.ProjectContract.objects.all()
    filter_class = filters.ProjectContractFilter
    permission_classes = (permissions.DjangoModelPermissions,)
    serializer_class = serializers.ProjectContractSerializer


class ConsultancyContractViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows consultancy contracts to be viewed or edited."""
    queryset = models.ConsultancyContract.objects.all()
    filter_class = filters.ConsultancyContractFilter
    permission_classes = (permissions.DjangoModelPermissions,)
    serializer_class = serializers.ConsultancyContractSerializer


class SupportContractViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows support contracts to be viewed or edited."""

    queryset = models.SupportContract.objects.all()
    filter_class = filters.SupportContractFilter
    permission_classes = (permissions.DjangoModelPermissions,)
    serializer_class = serializers.SupportContractSerializer


class ContractRoleViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows contract roles to be viewed."""

    queryset = models.ContractRole.objects.all()
    serializer_class = serializers.ContractRoleSerializer
    filter_class = filters.ContractRoleFilter
    permission_classes = (permissions.IsAuthenticated,)


class UserInfoViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows user info to be viewed."""

    queryset = models.UserInfo.objects.all()
    serializer_class = serializers.UserInfoSerializer
    filter_class = filters.UserInfoFilter
    permission_classes = (permissions.IsAuthenticated,)


class ContractUserViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows contract users to be viewed."""

    queryset = models.ContractUser.objects.all()
    serializer_class = serializers.ContractUserSerializer
    filter_class = filters.ContractUserFilter
    permission_classes = (permissions.IsAuthenticated,)


class ContractGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows contract groups to be viewed."""

    queryset = models.ContractGroup.objects.all()
    serializer_class = serializers.ContractGroupSerializer
    filter_class = filters.ContractGroupFilter
    permission_classes = (permissions.IsAuthenticated,)


class PerformanceImportServiceAPIView(APIView):
    """Gets performances from external sources and returns them to be imported."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, format=None):
        from_date = request.query_params.get('from', str(date.today()))
        to_date = request.query_params.get('to', str(date.today()))

        data = []

        # Redmine
        redmine_data = redmine.get_user_redmine_performances(request.user, from_date=from_date, to_date=to_date)
        data += redmine_data

        return Response(data)


class RangeAvailabilityServiceAPIView(APIView):
    """Get availability for all active users."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, format=None):
        """Defines the entrypoint of the retrieval."""
        from_date = parser.parse(request.query_params.get('from', None)).date()
        until_date = parser.parse(request.query_params.get('until', None)).date()

        users = auth_models.User.objects.filter(is_active=True)
        sickness_type_ids = list(models.LeaveType.objects.filter(name__icontains='sick').values_list('id', flat=True))

        # Initialize data
        data = {
            'from': from_date,
            'until': until_date,
            'no_work': {},
            'holiday': {},
            'home_work': {},
            'sickness': {},
            'leave': {}
        }

        # Fetch all employment contracts for this period
        employment_contracts = (models.EmploymentContract.objects
                                .filter(
                                    (Q(ended_at__isnull=True) & Q(started_at__lte=until_date)) |
                                    (Q(started_at__lte=until_date) & Q(ended_at__gte=from_date)),
                                    user__in=users)
                                .order_by('started_at')
                                .select_related('user', 'company', 'work_schedule'))
        # Index employment contracts by user ID
        employment_contract_data = {}
        for employment_contract in employment_contracts:
            (employment_contract_data
                .setdefault(employment_contract.user.id, [])
                .append(employment_contract))

        # Fetch all leave dates for this period
        leave_dates = (models.LeaveDate.objects
                       .filter(leave__user__in=users, leave__status=models.STATUS_APPROVED,
                               starts_at__date__gte=from_date, starts_at__date__lte=until_date)
                       .select_related('leave', 'leave__leave_type', 'leave__user'))
        # Index leave dates by day, then by user ID
        leave_date_data = {}
        for leave_date in leave_dates:
            (leave_date_data
                .setdefault(str(leave_date.starts_at.date()), {})
                .setdefault(leave_date.leave.user.id, [])
                .append(leave_date))

        # Fetch all holidays for this period
        holidays = (models.Holiday.objects
                    .filter(date__gte=from_date, date__lte=until_date))
        # Index holidays by day, then by country
        holiday_data = {}
        for holiday in holidays:
            (holiday_data
                .setdefault(str(holiday.date), {})
                .setdefault(holiday.country, [])
                .append(holiday))

        # Count days
        day_count = (until_date - from_date).days + 1

        # Iterate over users
        for user in users:
            # Initialize user data
            user_no_work = []
            user_holiday = []
            user_home_work = []
            user_sickness = []
            user_leave = []

            # Iterate over days
            for i in range(day_count):
                # Determine date for this day
                current_date = copy.deepcopy(from_date) + timedelta(days=i)

                # Get employment contract for this day
                # This allows us to determine the work schedule and country of the user
                employment_contract = None
                try:
                    for ec in employment_contract_data[user.id]:
                        if (ec.started_at <= current_date) and ((not ec.ended_at) or (ec.ended_at >= current_date)):
                            employment_contract = ec
                            break
                except KeyError:
                    pass

                work_schedule = employment_contract.work_schedule if employment_contract else None
                country = employment_contract.company.country if employment_contract else None

                # No work occurs when there is no work_schedule, or no hours should be worked that day
                if (not work_schedule) or (getattr(work_schedule, current_date.strftime('%A').lower(), 0.00) <= 0):
                    user_no_work.append(current_date)

                # Holidays
                try:
                    if country and holiday_data[str(current_date)][country]:
                        user_holiday.append(current_date)
                except KeyError:
                    pass

                # Leave & Sickness
                try:
                    for leave_date in leave_date_data[str(current_date)][user.id]:
                        if leave_date.leave.leave_type.id in sickness_type_ids:
                            user_sickness.append(current_date)
                        else:
                            user_leave.append(current_date)
                except KeyError:
                    pass

                # Home work
                # @TODO Implement home working

            # Store user data
            data['no_work'][user.id] = user_no_work
            data['holiday'][user.id] = user_holiday
            data['home_work'][user.id] = user_home_work
            data['sickness'][user.id] = user_sickness
            data['leave'][user.id] = user_leave

        return Response(data, status=status.HTTP_200_OK)


class RangeInfoServiceAPIView(APIView):
    """Calculates and returns information for a given date range."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, format=None):
        """Get date range information."""
        user = request.user

        from_date = parser.parse(request.query_params.get('from', None)).date()
        until_date = parser.parse(request.query_params.get('until', None)).date()
        daily = request.query_params.get('daily', 'false') == 'true'
        detailed = request.query_params.get('detailed', 'false') == 'true'
        summary = request.query_params.get('summary', 'false') == 'true'

        data = calculation.get_range_info([user], from_date, until_date, daily=daily, detailed=detailed,
                                          summary=summary, serialize=True)
        data = data[user.id]

        return Response(data)


class MyUserServiceAPIView(APIView):
    """Get the currently authenticated user."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, format=None):
        entity = request.user
        data = serializers.MyUserSerializer(entity, context={'request': request}).data

        return Response(data)


class LeaveRequestServiceAPIView(APIView):
    """Request leave for the given date range."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, format=None):
        user = request.user
        leave_type = get_object_or_404(models.LeaveType, pk=request.data['leave_type'])
        description = request.data.get('description', None)
        full_day = request.data.get('full_day', False)

        starts_at = parser.parse(request.data['starts_at'])
        starts_at = timezone.make_aware(starts_at) if not timezone.is_aware(starts_at) else starts_at
        ends_at = parser.parse(request.data['ends_at'])
        ends_at = timezone.make_aware(ends_at) if not timezone.is_aware(ends_at) else ends_at

        # If the end date comes before the start date, NOPE
        if ends_at < starts_at:
            raise serializers.ValidationError(_('The end date should come after the start date.'))

        # Ensure we can roll back if something goes wrong
        with transaction.atomic():
            # Create leave
            leave = models.Leave.objects.create(user=user, description=description, leave_type=leave_type,
                                                status=models.STATUS_DRAFT)

            # Determine leave dates to create
            leave_dates = []

            # If this isn't a full day request, we have a single pair
            if not full_day:
                leave_dates.append([starts_at, ends_at])

            # If this is a full day request, determine leave date pairs using work schedule
            else:
                # Determine amount of days we are going to create leaves for, so we can
                # iterate over the dates
                leave_date_count = (ends_at - starts_at).days + 1

                work_schedule = None
                employment_contract = None

                for i in range(leave_date_count):
                    # Determine date for this day
                    current_dt = copy.deepcopy(starts_at) + timedelta(days=i)
                    current_date = current_dt.date()

                    # For the given date, determine the active work schedule
                    if ((not employment_contract) or (employment_contract.started_at > current_date) or
                            (employment_contract.ended_at and (employment_contract.ended_at < current_date))):
                        employment_contract = models.EmploymentContract.objects.filter(
                            Q(user=user, started_at__lte=current_date) &
                            (Q(ended_at__isnull=True) | Q(ended_at__gte=current_date))
                        ).first()
                        work_schedule = employment_contract.work_schedule if employment_contract else None

                    # Determine amount of hours to work on this day based on work schedule
                    work_hours = 0.00
                    if work_schedule:
                        work_hours = float(getattr(work_schedule, current_date.strftime('%A').lower(), Decimal(0.00)))

                    # Determine existence of holidays on this day based on work schedule
                    holiday = None
                    if employment_contract:
                        holiday = models.Holiday.objects.filter(date=current_date,
                                                                country=employment_contract.company.country).first()

                    # If we have to work a certain amount of hours on this day, and there is no holiday on that day,
                    # add a leave date pair for that amount of hours
                    if (work_hours > 0.0) and (not holiday):
                        # Ensure the leave starts when the working day does
                        pair_starts_at = current_dt.replace(hour=settings.DEFAULT_WORKING_DAY_STARTING_HOUR, minute=0,
                                                            second=0)
                        # Add work hours to pair start to obtain pair end
                        pair_ends_at = pair_starts_at.replace(hour=int(pair_starts_at.hour + work_hours),
                                                              minute=int((work_hours % 1) * 60))
                        # Log pair
                        leave_dates.append([pair_starts_at, pair_ends_at])

            # If no leave date pairs are available, no leave should be created
            if not leave_dates:
                raise serializers.ValidationError(_('No leave dates are available for this period.'))

            # Create leave dates for leave date pairs
            timesheet = None
            for pair in leave_dates:
                # Determine timesheet to use
                if (not timesheet) or ((timesheet.year != pair[0].year) or (timesheet.month != pair[0].month)):
                    timesheet, created = models.Timesheet.objects.get_or_create(user=user, year=pair[0].year,
                                                                                month=pair[0].month)

                models.LeaveDate.objects.create(leave=leave, timesheet=timesheet, starts_at=pair[0],
                                                ends_at=pair[1])

            # Mark leave as Pending
            leave.status = models.STATUS_PENDING
            leave.save()

        data = serializers.MyLeaveSerializer(leave, context={'request': request}).data

        return Response(data)


class MyTimesheetContractPdfExportServiceAPIView(BaseTimesheetContractPdfExportServiceAPIView):
    """Export a timesheet contract to PDF."""

    permission_classes = (permissions.IsAuthenticated,)

    def resolve_user(self, context):
        """Resolve the user for this export."""
        return context['view'].request.user


class MyLeaveViewSet(viewsets.ModelViewSet):
    """API endpoint that allows leaves for the currently authenticated user to be viewed or edited."""

    serializer_class = serializers.MyLeaveSerializer
    filter_class = filters.LeaveFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return user.leave_set.all()


class MyLeaveDateViewSet(viewsets.ModelViewSet):
    """API endpoint that allows leave dates for the currently authenticated user to be viewed or edited."""

    serializer_class = serializers.MyLeaveDateSerializer
    filter_class = filters.LeaveDateFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return models.LeaveDate.objects.filter(leave__user=user)


class MyTimesheetViewSet(viewsets.ModelViewSet):
    """API endpoint that allows timesheets for the currently authenticated user to be viewed or edited."""

    serializer_class = serializers.MyTimesheetSerializer
    filter_class = filters.TimesheetFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return self.request.user.timesheet_set

    def perform_destroy(self, instance):
        if instance.status != models.STATUS_ACTIVE:
            raise serializers.ValidationError({'status': _('Only active timesheets can be deleted.')})

        return super().perform_destroy(instance)


class MyContractViewSet(GenericHierarchicalReadOnlyViewSet):
    """API endpoint that allows contracts for the currently authenticated user to be viewed."""

    serializer_class = serializers.ContractSerializer
    serializer_classes = {
        models.ProjectContract: serializers.ProjectContractSerializer,
        models.ConsultancyContract: serializers.ConsultancyContractSerializer,
        models.SupportContract: serializers.SupportContractSerializer,
    }
    filter_class = filters.ContractFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return models.Contract.objects.filter(contractuser__user=user).distinct()


class MyContractUserViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows contract users for the currently authenticated user to be viewed."""

    serializer_class = serializers.MyContractUserSerializer
    filter_class = filters.ContractUserFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return models.ContractUser.objects.filter(user=user).distinct()


class MyPerformanceViewSet(GenericHierarchicalReadOnlyViewSet):
    """API endpoint that allows performances for the currently authenticated user to be viewed or edited."""

    serializer_class = serializers.MyPerformanceSerializer
    serializer_classes = {
        models.StandbyPerformance: serializers.MyStandbyPerformanceSerializer,
        models.ActivityPerformance: serializers.MyActivityPerformanceSerializer,
    }
    filter_class = filters.PerformanceFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return models.Performance.objects.filter(timesheet__user=user)


class MyActivityPerformanceViewSet(viewsets.ModelViewSet):
    """API endpoint that allows activity performances for the currently authenticated user to be viewed or edited."""

    serializer_class = serializers.MyActivityPerformanceSerializer
    filter_class = filters.ActivityPerformanceFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return models.ActivityPerformance.objects.filter(timesheet__user=user)


class MyStandbyPerformanceViewSet(viewsets.ModelViewSet):
    """API endpoint that allows standby performances for the currently authenticated user to be viewed or edited."""

    serializer_class = serializers.MyStandbyPerformanceSerializer
    filter_class = filters.StandbyPerformanceFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return models.StandbyPerformance.objects.filter(timesheet__user=user)


class MyAttachmentViewSet(viewsets.ModelViewSet):
    """API endpoint that allows attachments for the currently authenticated user to be viewed or edited."""

    serializer_class = serializers.MyAttachmentSerializer
    filter_class = filters.AttachmentFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return user.attachment_set.all()


class MyWorkScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint that allows workschedules for the currently authenticated user to be viewed or edited."""

    serializer_class = serializers.MyWorkScheduleSerializer
    filter_class = filters.WorkScheduleFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return models.WorkSchedule.objects.filter(employmentcontract__user=user)


class LeaveFeedServiceAPIView(APIView):
    """Get leaves as an ICS feed."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, format=None):
        return feeds.LeaveFeed().__call__(request)
