import re
from django.db import models
from django.db import transaction
from apps.registrations.models import Customer, Registration

def normalize_phone(phone_val):
    """Normalizes phone number to 10 digits"""
    if not phone_val:
        return ''
    digits = re.sub(r'\D', '', str(phone_val))
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    return digits

def normalize_email(email_val):
    """Normalizes email address to lower-case stripped string"""
    if not email_val:
        return ''
    return str(email_val).strip().lower()

def merge_customer_profiles(primary, duplicate):
    """
    Merges duplicate Customer profile into primary Customer profile.
    - Preserves all Registrations by re-linking them to primary.
    - Preserves and consolidates metadata (name, phone, email, company, designation).
    - Safely deletes duplicate.
    """
    if not primary or not duplicate or primary.id == duplicate.id:
        return primary

    with transaction.atomic():
        # 1. Transfer all registrations from duplicate to primary
        Registration.objects.filter(customer=duplicate).update(customer=primary)

        # 2. Consolidate metadata
        if not primary.name and duplicate.name:
            primary.name = duplicate.name

        # Prefer non-empty and well-formed phone
        if not primary.phone and duplicate.phone:
            primary.phone = duplicate.phone

        # Prefer valid email if primary has placeholder or malformed email
        if not primary.email and duplicate.email:
            primary.email = duplicate.email
        elif duplicate.email and ('@' in duplicate.email and '.' in duplicate.email) and ('.' not in primary.email):
            primary.email = duplicate.email

        if not primary.company and duplicate.company:
            primary.company = duplicate.company

        if not primary.designation and duplicate.designation:
            primary.designation = duplicate.designation

        primary.save()

        # 3. Delete the duplicate profile from database
        duplicate.delete()

    return primary

def get_or_merge_customer(tenant, phone=None, email=None, name='', company='', designation=''):
    """
    Finds or creates a Customer profile for a tenant in the database.
    Strictly uses phone number as the primary identifier to link customer accounts in the database.
    If phone number matches an existing customer profile, links the registration to that account.
    """
    clean_phone = normalize_phone(phone)
    clean_email = normalize_email(email)

    with transaction.atomic():
        primary = None
        if clean_phone:
            # Match strictly by phone number as primary identifier in the database
            primary = Customer.objects.filter(tenant=tenant, phone=clean_phone).order_by('created_at').first()
            if primary:
                # Merge any duplicate records for this exact phone
                duplicates = list(Customer.objects.filter(tenant=tenant, phone=clean_phone).exclude(id=primary.id))
                for dup in duplicates:
                    merge_customer_profiles(primary, dup)
        elif clean_email:
            # Fallback only when phone is not provided
            primary = Customer.objects.filter(tenant=tenant, email__iexact=clean_email).order_by('created_at').first()

        if not primary:
            # Create fresh customer profile
            primary = Customer.objects.create(
                tenant=tenant,
                phone=clean_phone or '',
                email=clean_email or '',
                name=name or 'Attendee',
                company=company or '',
                designation=designation or ''
            )
            return primary

        # Update primary with latest provided details
        if name and name.strip():
            primary.name = name.strip()
        if clean_phone:
            primary.phone = clean_phone
        if clean_email:
            primary.email = clean_email
        if company and company.strip():
            primary.company = company.strip()
        if designation and designation.strip():
            primary.designation = designation.strip()

        primary.save()
        return primary

def consolidate_tenant_customers(tenant):
    """
    Scans the database for any existing duplicate Customer profiles for this tenant:
    - Profiles sharing the same mobile number with different emails
    - Profiles sharing the same email ID with different mobile numbers
    Merges all matching profiles so only one unified profile remains in the database.
    Returns the number of duplicate profiles removed.
    """
    all_customers = list(Customer.objects.filter(tenant=tenant).order_by('created_at'))
    if len(all_customers) <= 1:
        return 0

    # Build disjoint-set (Union-Find)
    parent = {c.id: c.id for c in all_customers}
    cust_map = {c.id: c for c in all_customers}

    def find(i):
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            # Keep the smaller (earlier created) ID as root
            if root_i < root_j:
                parent[root_j] = root_i
            else:
                parent[root_i] = root_j

    phone_map = {}
    email_map = {}

    for c in all_customers:
        p = normalize_phone(c.phone)
        e = normalize_email(c.email)

        if p:
            if p in phone_map:
                union(phone_map[p], c.id)
            else:
                phone_map[p] = c.id

        if e:
            if e in email_map:
                union(email_map[e], c.id)
            else:
                email_map[e] = c.id

    # Group customers by root
    groups = {}
    for c in all_customers:
        root_id = find(c.id)
        groups.setdefault(root_id, []).append(c)

    merged_count = 0
    with transaction.atomic():
        for root_id, group in groups.items():
            if len(group) > 1:
                primary = cust_map[root_id]
                for duplicate in group:
                    if duplicate.id != primary.id:
                        # Merge duplicate into primary
                        merge_customer_profiles(primary, duplicate)
                        merged_count += 1

    return merged_count
