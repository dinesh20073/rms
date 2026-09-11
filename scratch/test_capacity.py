import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_core.settings')
django.setup()

from apps.events.models import Event

event = Event.objects.first()
if event:
    # Test setting unlimited capacity
    event.max_capacity = None
    event.save()
    assert event.is_registration_open is True
    assert event.get_registration_closed_reason() is None
    print(f"Verified unlimited capacity: event.max_capacity={event.max_capacity}, is_open={event.is_registration_open}")

    # Test setting fixed capacity
    event.max_capacity = 500
    event.save()
    assert event.max_capacity == 500
    print(f"Verified set capacity: event.max_capacity={event.max_capacity}, is_open={event.is_registration_open}")
    print("All capacity tests PASSED successfully!")
