'use client';

import { useState, useEffect } from 'react';

interface MediaItem {
  id: string;
  title: string;
  description: string;
  url: string;
  category: string;
  media_type: 'image' | 'video' | 'link';
  sort_order: number;
  is_published: boolean;
  created_at: string;
}

export default function MediaDashboardPage() {
  const [apiKey, setApiKey] = useState('nizhal-super-secret-admin-key-2026');
  const [mediaList, setMediaList] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    url: '',
    category: 'general',
    media_type: 'image',
    sort_order: 0,
    is_published: true,
  });

  // Load API Key from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('NIZHAL_ADMIN_API_KEY');
    if (saved) setApiKey(saved);
  }, []);

  const saveApiKey = (key: string) => {
    setApiKey(key);
    localStorage.setItem('NIZHAL_ADMIN_API_KEY', key);
  };

  // Fetch Media
  const fetchMedia = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/media?admin=true`, {
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
      });

      if (!res.ok) {
        const pubRes = await fetch(`/api/media`);
        if (!pubRes.ok) throw new Error('Failed to fetch media');
        const pubData = await pubRes.json();
        setMediaList(pubData.media || []);
      } else {
        const data = await res.json();
        setMediaList(data.media || []);
      }
    } catch (err: any) {
      setError(err.message || 'Error loading media');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMedia();
  }, [apiKey]);

  // Handle Create
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/media', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify(formData),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Failed to add media');
      }

      setSuccessMsg('Memory added successfully! ♡');
      setTimeout(() => setSuccessMsg(null), 4000);
      setIsModalOpen(false);
      setFormData({
        title: '',
        description: '',
        url: '',
        category: 'general',
        media_type: 'image',
        sort_order: 0,
        is_published: true,
      });
      fetchMedia();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setFormLoading(false);
    }
  };

  // Toggle Hide / Unhide
  const handleTogglePublish = async (item: MediaItem) => {
    try {
      const res = await fetch('/api/media', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          id: item.id,
          is_published: !item.is_published,
        }),
      });

      if (!res.ok) throw new Error('Failed to update status');
      setMediaList((prev) =>
        prev.map((m) => (m.id === item.id ? { ...m, is_published: !m.is_published } : m))
      );
    } catch (err: any) {
      alert('Error updating: ' + err.message);
    }
  };

  // Delete
  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`Are you sure you want to delete "${title}"?`)) return;

    try {
      const res = await fetch(`/api/media?id=${id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
      });

      if (!res.ok) throw new Error('Failed to delete item');
      setMediaList((prev) => prev.filter((m) => m.id !== id));
      setSuccessMsg('Memory deleted successfully.');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      alert('Delete error: ' + err.message);
    }
  };

  const totalCount = mediaList.length;
  const imageCount = mediaList.filter((m) => m.media_type === 'image').length;
  const videoCount = mediaList.filter((m) => m.media_type === 'video').length;
  const hiddenCount = mediaList.filter((m) => !m.is_published).length;

  const getPreviewUrl = (url: string) => {
    if (!url) return '';
    if (url.includes('drive.google.com')) {
      const match = url.match(/\/file\/d\/([a-zA-Z0-9_-]+)/) || url.match(/[?&]id=([a-zA-Z0-9_-]+)/);
      if (match) return `https://lh3.googleusercontent.com/d/${match[1]}=w400`;
    }
    return url;
  };

  return (
    <div style={{ minHeight: '100vh', background: '#0b1120', color: '#f8fafc', padding: '32px 20px', fontFamily: 'inherit' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        
        {/* Top Header */}
        <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '16px', marginBottom: '28px', borderBottom: '1px solid #1e293b', paddingBottom: '20px' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: '#38bdf8', background: '#0c4a6e', padding: '4px 12px', borderRadius: '9999px', fontSize: '12px', fontWeight: 600, marginBottom: '8px' }}>
              <span>●</span> Nizhal Scrapbook Control Console
            </div>
            <h1 style={{ fontSize: '28px', fontWeight: 700, letterSpacing: '-0.5px' }}>
              Scrapbook Memories Manager
            </h1>
            <p style={{ color: '#94a3b8', fontSize: '14px', marginTop: '4px' }}>
              Manage photos, videos, and Google Drive memories in Supabase PostgreSQL.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              onClick={() => setIsModalOpen(true)}
              style={{
                background: '#1a73e8',
                color: '#ffffff',
                border: 'none',
                padding: '10px 20px',
                borderRadius: '8px',
                fontWeight: 600,
                fontSize: '14px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: '0 4px 14px rgba(26, 115, 232, 0.4)',
              }}
            >
              <span>+</span> Add New Memory
            </button>
          </div>
        </header>

        {/* Status / Alert Banners */}
        {error && (
          <div style={{ background: '#450a0a', border: '1px solid #991b1b', color: '#fecaca', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', fontSize: '14px' }}>
            ⚠️ {error}
          </div>
        )}
        {successMsg && (
          <div style={{ background: '#052e16', border: '1px solid #166534', color: '#bbf7d0', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', fontSize: '14px' }}>
            ✓ {successMsg}
          </div>
        )}

        {/* 4 Stats Cards: Images, Video, Total, Hidden */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', padding: '16px' }}>
            <span style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Total</span>
            <div style={{ fontSize: '28px', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>{totalCount}</div>
            <span style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', display: 'block' }}>All memories</span>
          </div>

          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', padding: '16px' }}>
            <span style={{ fontSize: '12px', color: '#38bdf8', textTransform: 'uppercase', fontWeight: 600 }}>Images</span>
            <div style={{ fontSize: '28px', fontWeight: 700, color: '#38bdf8', marginTop: '4px' }}>{imageCount}</div>
            <span style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', display: 'block' }}>Photos & polaroids</span>
          </div>

          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', padding: '16px' }}>
            <span style={{ fontSize: '12px', color: '#fbbf24', textTransform: 'uppercase', fontWeight: 600 }}>Video</span>
            <div style={{ fontSize: '28px', fontWeight: 700, color: '#fbbf24', marginTop: '4px' }}>{videoCount}</div>
            <span style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', display: 'block' }}>Video clips</span>
          </div>

          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', padding: '16px' }}>
            <span style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Total Hidden</span>
            <div style={{ fontSize: '28px', fontWeight: 700, color: '#94a3b8', marginTop: '4px' }}>{hiddenCount}</div>
            <span style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', display: 'block' }}>Hidden from users</span>
          </div>
        </div>

        {/* Media Grid */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: '#94a3b8' }}>
            Loading scrapbook memories from Supabase...
          </div>
        ) : mediaList.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', background: '#1e293b', borderRadius: '12px', border: '1px solid #334155' }}>
            <p style={{ color: '#94a3b8', fontSize: '16px', marginBottom: '12px' }}>No memories added yet.</p>
            <button
              onClick={() => setIsModalOpen(true)}
              style={{ background: '#1a73e8', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}
            >
              Add First Memory
            </button>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
            {mediaList.map((item) => (
              <div
                key={item.id}
                style={{
                  background: '#1e293b',
                  border: '1px solid #334155',
                  borderTop: item.is_published ? '3px solid #16a34a' : '3px solid #64748b',
                  borderRadius: '12px',
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                {/* Media Preview Box */}
                <div style={{ position: 'relative', width: '100%', height: '200px', background: '#0f172a', overflow: 'hidden' }}>
                  {item.media_type === 'video' ? (
                    <video
                      src={item.url}
                      controls
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  ) : (
                    <img
                      src={getPreviewUrl(item.url)}
                      alt={item.title}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={(e: any) => {
                        e.target.src = 'https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=600&q=80';
                      }}
                    />
                  )}

                  <div style={{ position: 'absolute', top: '10px', left: '10px', display: 'flex', gap: '6px' }}>
                    <span style={{ background: '#3b82f6', color: '#fff', fontSize: '11px', padding: '3px 8px', borderRadius: '4px', textTransform: 'uppercase', fontWeight: 600 }}>
                      {item.media_type}
                    </span>
                    <span style={{ background: item.is_published ? '#16a34a' : '#475569', color: '#fff', fontSize: '11px', padding: '3px 8px', borderRadius: '4px', fontWeight: 600 }}>
                      {item.is_published ? '● Live' : '○ Hidden'}
                    </span>
                  </div>
                </div>

                {/* Card Content */}
                <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', flex: 1 }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f8fafc', marginBottom: '6px' }}>{item.title}</h3>
                  <p style={{ fontSize: '14px', color: '#94a3b8', fontStyle: 'italic', marginBottom: '12px', flex: 1 }}>
                    &ldquo;{item.description || 'No caption'}&rdquo;
                  </p>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid #334155', paddingTop: '12px', fontSize: '12px', color: '#64748b' }}>
                    <button
                      onClick={() => handleTogglePublish(item)}
                      style={{
                        background: '#0f172a',
                        border: '1px solid #334155',
                        color: item.is_published ? '#e2e8f0' : '#4ade80',
                        padding: '4px 10px',
                        borderRadius: '6px',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      {item.is_published ? 'Hide' : 'Unhide'}
                    </button>

                    <div style={{ display: 'flex', gap: '8px' }}>
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ color: '#38bdf8', textDecoration: 'none', padding: '4px 8px', background: '#0f172a', borderRadius: '4px' }}
                      >
                        View
                      </a>
                      <button
                        onClick={() => handleDelete(item.id, item.title)}
                        style={{ background: '#7f1d1d', color: '#fca5a5', border: 'none', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer' }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Modal: Add New Memory */}
        {isModalOpen && (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.75)',
              backdropFilter: 'blur(4px)',
              zIndex: 100,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '20px',
            }}
          >
            <div
              style={{
                background: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '16px',
                maxWidth: '520px',
                width: '100%',
                maxHeight: '90vh',
                overflowY: 'auto',
                padding: '24px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#f8fafc' }}>Add Scrapbook Memory</h2>
                <button
                  onClick={() => setIsModalOpen(false)}
                  style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '20px', cursor: 'pointer' }}
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                    Title *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    placeholder="e.g. Sunset Circle by the Beach"
                    style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '10px 14px', color: '#fff', fontSize: '14px' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                    Media URL * (HTTPS or Google Drive link)
                  </label>
                  <input
                    type="url"
                    required
                    value={formData.url}
                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                    placeholder="https://... or Google Drive share link"
                    style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '10px 14px', color: '#fff', fontSize: '14px' }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                      Media Type
                    </label>
                    <select
                      value={formData.media_type}
                      onChange={(e) => setFormData({ ...formData, media_type: e.target.value as any })}
                      style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '10px 14px', color: '#fff', fontSize: '14px' }}
                    >
                      <option value="image">Photo / Image</option>
                      <option value="video">Video (MP4 / Drive)</option>
                      <option value="link">Link / Post</option>
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                      Priority
                    </label>
                    <input
                      type="number"
                      value={formData.sort_order}
                      onChange={(e) => setFormData({ ...formData, sort_order: parseInt(e.target.value, 10) || 0 })}
                      style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '10px 14px', color: '#fff', fontSize: '14px' }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                    Handwritten Note / Caption
                  </label>
                  <textarea
                    rows={3}
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="listening deeply, warmth & good souls ♡"
                    style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '10px 14px', color: '#fff', fontSize: '14px' }}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="checkbox"
                    id="isPublishedModal"
                    checked={formData.is_published}
                    onChange={(e) => setFormData({ ...formData, is_published: e.target.checked })}
                    style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                  />
                  <label htmlFor="isPublishedModal" style={{ fontSize: '13px', color: '#f8fafc', cursor: 'pointer' }}>
                    Live on Scrapbook (Uncheck to keep hidden)
                  </label>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '16px' }}>
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    style={{ background: '#334155', color: '#fff', border: 'none', padding: '10px 18px', borderRadius: '8px', cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={formLoading}
                    style={{ background: '#1a73e8', color: '#fff', border: 'none', padding: '10px 22px', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}
                  >
                    {formLoading ? 'Saving...' : 'Save Memory'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
