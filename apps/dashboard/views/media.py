from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection
from apps.dashboard.views.overview import get_current_tenant

@login_required(login_url='dashboard-login')
def media_dashboard_view(request):
    current_tenant = get_current_tenant(request)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            title = request.POST.get('title', '').strip()
            url = request.POST.get('url', '').strip()
            description = request.POST.get('description', '').strip()
            category = 'general'
            media_type = request.POST.get('media_type', 'image').strip()
            try:
                sort_order = int(request.POST.get('sort_order', 0))
            except ValueError:
                sort_order = 0
            is_published = request.POST.get('is_published') == 'on'

            if not title or not url:
                messages.error(request, 'Title and URL are required.')
            elif not url.startswith('https://'):
                messages.error(request, 'URL must use HTTPS protocol.')
            else:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO public.media (title, description, url, category, media_type, sort_order, is_published)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, [title, description, url, category, media_type, sort_order, is_published])
                    messages.success(request, f'Memory "{title}" added successfully! ♡')
                except Exception as e:
                    messages.error(request, f'Error adding memory: {str(e)}')
            return redirect('dashboard-media')

        elif action in ('update', 'edit'):
            media_id = request.POST.get('media_id', '').strip()
            title = request.POST.get('title', '').strip()
            url = request.POST.get('url', '').strip()
            description = request.POST.get('description', '').strip()
            media_type = request.POST.get('media_type', 'image').strip()
            try:
                sort_order = int(request.POST.get('sort_order', 0))
            except ValueError:
                sort_order = 0
            is_published = request.POST.get('is_published') == 'on'

            if not media_id or not title or not url:
                messages.error(request, 'Memory ID, Title, and URL are required.')
            elif not url.startswith('https://'):
                messages.error(request, 'URL must use HTTPS protocol.')
            else:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            UPDATE public.media
                            SET title = %s, description = %s, url = %s, media_type = %s, sort_order = %s, is_published = %s
                            WHERE id = %s
                        """, [title, description, url, media_type, sort_order, is_published, media_id])
                    messages.success(request, f'Memory "{title}" updated successfully! ♡')
                except Exception as e:
                    messages.error(request, f'Error updating memory: {str(e)}')
            return redirect('dashboard-media')

        elif action == 'toggle_publish':
            media_id = request.POST.get('media_id')
            if media_id:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            UPDATE public.media
                            SET is_published = NOT is_published
                            WHERE id = %s
                        """, [media_id])
                    messages.success(request, 'Visibility status updated.')
                except Exception as e:
                    messages.error(request, f'Failed to update status: {str(e)}')
            return redirect('dashboard-media')

        elif action == 'delete':
            media_id = request.POST.get('media_id')
            if media_id:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM public.media WHERE id = %s", [media_id])
                    messages.success(request, 'Memory removed from scrapbook.')
                except Exception as e:
                    messages.error(request, f'Delete error: {str(e)}')
            return redirect('dashboard-media')

    # GET Request: Fetch all media records
    media_list = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, title, description, url, category, media_type, sort_order, is_published, created_at
                FROM public.media
                ORDER BY sort_order ASC, created_at DESC;
            """)
            rows = cursor.fetchall()
            for r in rows:
                url_val = r[3]
                preview_url = url_val
                if 'drive.google.com' in url_val:
                    import re
                    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url_val) or re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url_val)
                    if match:
                        preview_url = f"https://lh3.googleusercontent.com/d/{match.group(1)}=w400"

                media_list.append({
                    'id': str(r[0]),
                    'title': r[1],
                    'description': r[2],
                    'url': url_val,
                    'preview_url': preview_url,
                    'category': r[4],
                    'media_type': r[5],
                    'sort_order': r[6],
                    'is_published': r[7],
                    'created_at': r[8],
                })
    except Exception as e:
        messages.error(request, f'Failed to load media records: {str(e)}')

    # Stats requested: images, video, total, hidden
    total_count = len(media_list)
    image_count = sum(1 for m in media_list if m['media_type'] == 'image')
    video_count = sum(1 for m in media_list if m['media_type'] == 'video')
    hidden_count = sum(1 for m in media_list if not m['is_published'])

    context = {
        'current_tenant': current_tenant,
        'media_list': media_list,
        'total_count': total_count,
        'image_count': image_count,
        'video_count': video_count,
        'hidden_count': hidden_count,
    }
    return render(request, 'dashboard/media/index.html', context)
