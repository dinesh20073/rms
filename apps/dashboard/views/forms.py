import base64
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.text import slugify

from apps.events.models import Event
from apps.forms_builder.models import Form, FormField
from apps.audit.services import log_audit_event
from apps.dashboard.views.overview import get_current_tenant


@login_required(login_url='login')
def forms_list_view(request):
    return redirect('dashboard-events-list')


@login_required(login_url='login')
def form_builder_view(request, event_id):
    tenant = get_current_tenant(request)
    event = get_object_or_404(Event, id=event_id, tenant=tenant)
    form_obj, created = Form.objects.get_or_create(event=event)
    if created or not form_obj.fields.exists():
        form_obj.create_default_fields()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_field':
            label = request.POST.get('label', '').strip()
            field_type = request.POST.get('field_type', 'text')
            is_required = request.POST.get('is_required') == 'on'
            placeholder = request.POST.get('placeholder', '')
            options_raw = request.POST.get('options_csv', '')
            options = [o.strip() for o in options_raw.split(',') if o.strip()]

            order_num = form_obj.fields.count() + 1
            base_key = slugify(label).replace('-', '_') or 'field'
            field_key = base_key
            counter = 1
            while FormField.objects.filter(form=form_obj, field_key=field_key).exists():
                counter += 1
                field_key = f"{base_key}_{counter}"

            FormField.objects.create(
                form=form_obj,
                label=label,
                field_key=field_key,
                field_type=field_type,
                is_required=is_required,
                placeholder=placeholder,
                options=options,
                order=order_num
            )
            messages.success(request, f"Added question '{label}' to form.")
            return redirect('dashboard-event-form', event_id=event.id)

        elif action == 'edit_field':
            field_id = request.POST.get('field_id')
            field = get_object_or_404(FormField, id=field_id, form=form_obj)
            label = request.POST.get('label', '').strip()
            field_type = request.POST.get('field_type', field.field_type)
            is_required = request.POST.get('is_required') == 'on'
            placeholder = request.POST.get('placeholder', '')
            options_raw = request.POST.get('options_csv', '')
            options = [o.strip() for o in options_raw.split(',') if o.strip()]

            if label:
                field.label = label
            field.field_type = field_type
            field.is_required = is_required
            field.placeholder = placeholder
            field.options = options
            field.save()

            messages.success(request, f"Question '{field.label}' updated successfully.")
            return redirect('dashboard-event-form', event_id=event.id)

        elif action == 'delete_field':
            field_id = request.POST.get('field_id')
            FormField.objects.filter(id=field_id, form=form_obj).delete()
            messages.info(request, "Field removed from form.")
            return redirect('dashboard-event-form', event_id=event.id)

        elif action == 'clear_form':
            form_obj.fields.all().delete()
            messages.info(request, "All questions cleared from form.")
            return redirect('dashboard-event-form', event_id=event.id)

        elif action == 'reset_defaults':
            form_obj.fields.all().delete()
            form_obj.create_default_fields()
            messages.success(request, "Reset form to standard default questions.")
            return redirect('dashboard-event-form', event_id=event.id)

        elif action == 'upload_qr_code':
            if request.FILES.get('upi_qr_code'):
                qr_file = request.FILES['upi_qr_code']
                content = qr_file.read()
                qr_file.seek(0)
                b64 = base64.b64encode(content).decode('utf-8')
                name = str(getattr(qr_file, 'name', '')).lower()
                mime = 'image/png' if name.endswith('.png') else ('image/webp' if name.endswith('.webp') else 'image/jpeg')
                event.upi_qr_base64 = f"data:{mime};base64,{b64}"
                event.upi_qr_code = qr_file
                event.save()
                log_audit_event('EVENT_QR_UPDATED', event.event_code, {'mode': 'CUSTOM_UPLOAD'}, tenant=tenant, actor=request.user.username if request.user else 'Admin')
                messages.success(request, "Custom Payment QR code uploaded and embedded directly into database!")
            else:
                messages.warning(request, "Please select an image file to upload as QR code.")
            return redirect('dashboard-event-form', event_id=event.id)

        elif action == 'regenerate_qr':
            event.generate_master_event_qr()
            event.save()
            log_audit_event('EVENT_QR_REGENERATED', event.event_code, {'mode': 'DYNAMIC_UPI'}, tenant=tenant, actor=request.user.username if request.user else 'Admin')
            messages.success(request, "Dynamic Master UPI QR regenerated and embedded successfully into database!")
            return redirect('dashboard-event-form', event_id=event.id)

        elif action == 'update_form_settings':
            status_val = request.POST.get('status', 'OPEN')
            event.status = 'OPEN' if status_val == 'OPEN' else 'CLOSED'
            
            start_date_raw = request.POST.get('event_start_date', '').strip()
            reg_opens_raw = request.POST.get('registration_opens', '').strip()
            reg_closes_raw = request.POST.get('registration_closes', '').strip()
            max_capacity_raw = request.POST.get('max_capacity', '').strip()
            form_desc = request.POST.get('form_description', '').strip()
            event_venue = request.POST.get('venue', '').strip()

            if start_date_raw:
                try:
                    event.event_start_date = timezone.datetime.fromisoformat(start_date_raw)
                    if timezone.is_naive(event.event_start_date):
                        event.event_start_date = timezone.make_aware(event.event_start_date)
                except Exception:
                    pass
            else:
                event.event_start_date = None

            if reg_opens_raw:
                try:
                    event.registration_opens = timezone.datetime.fromisoformat(reg_opens_raw)
                    if timezone.is_naive(event.registration_opens):
                        event.registration_opens = timezone.make_aware(event.registration_opens)
                except Exception:
                    pass
            else:
                event.registration_opens = None
            
            if reg_closes_raw:
                try:
                    event.registration_closes = timezone.datetime.fromisoformat(reg_closes_raw)
                    if timezone.is_naive(event.registration_closes):
                        event.registration_closes = timezone.make_aware(event.registration_closes)
                except Exception:
                    pass
            else:
                event.registration_closes = None

            unlimited_cap = request.POST.get('unlimited_capacity') in ('1', 'true', 'on', True)
            if unlimited_cap or max_capacity_raw == '0' or not max_capacity_raw:
                event.max_capacity = None
            elif max_capacity_raw and str(max_capacity_raw).isdigit():
                event.max_capacity = int(max_capacity_raw)

            if event_venue:
                event.venue = event_venue

            event.save()

            if form_desc:
                form_obj.description = form_desc
                form_obj.save()

            messages.success(request, "Form response deadline and settings saved successfully.")
            return redirect('dashboard-event-form', event_id=event.id)

    fields = form_obj.fields.all()
    return render(request, 'dashboard/events/form_builder.html', {
        'event': event,
        'form_obj': form_obj,
        'fields': fields
    })
