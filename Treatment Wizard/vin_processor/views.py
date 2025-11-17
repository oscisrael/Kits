from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import VINProcessing
from .tasks import process_vin_task
import json


def home(request):
    """דף הבית - טופס הכנסת VIN"""
    return render(request, 'vin_processor/home.html')


@require_http_methods(["POST"])
def start_processing(request):
    """התחלת עיבוד VIN"""
    vin = request.POST.get('vin', '').strip().upper()

    # Validation
    if len(vin) != 17:
        return JsonResponse({'error': 'מספר VIN חייב להיות בדיוק 17 תווים'}, status=400)

    # Check if already exists
    vin_obj, created = VINProcessing.objects.get_or_create(
        vin=vin,
        defaults={'status': 'PENDING'}
    )

    if not created and vin_obj.status == 'COMPLETED':
        # Already processed - redirect to results
        return JsonResponse({'redirect': f'/results/{vin_obj.id}/'})

    # Start task
    process_vin_task.delay(vin_obj.id)

    return JsonResponse({'task_id': vin_obj.id})


def progress_status(request, task_id):
    """בדיקת סטטוס ה-progress"""
    vin_obj = get_object_or_404(VINProcessing, id=task_id)

    return JsonResponse({
        'status': vin_obj.status,
        'progress': vin_obj.progress,
        'current_step': vin_obj.current_step,
        'error_message': vin_obj.error_message,
    })


def results(request, task_id):
    """הצגת תוצאות"""
    vin_obj = get_object_or_404(VINProcessing, id=task_id)

    if vin_obj.status != 'COMPLETED':
        return redirect('home')

    result_data = vin_obj.get_result_dict()

    # Extract service data (excluding 'model' and 'oil_capacity')
    services = {}
    for key, value in result_data.items():
        if key not in ['model', 'oil_capacity']:
            services[key] = value

    context = {
        'vin': vin_obj.vin,
        'model': result_data.get('model', ''),
        'oil_capacity': result_data.get('oil_capacity', ''),
        'services': services,
    }

    return render(request, 'vin_processor/results.html', context)


from django.shortcuts import render

# Create your views here.
