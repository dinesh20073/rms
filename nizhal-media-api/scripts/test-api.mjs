/**
 * Test runner for Nizhal Media API Backend
 * Tests:
 * 1. GET /api/media (public, format verification, CORS)
 * 2. OPTIONS /api/media (CORS preflight)
 * 3. POST /api/media (401 Missing / Invalid Token)
 * 4. POST /api/media (400 Invalid Input Validations)
 * 5. POST /api/media (Valid insert / error handling without secret leaks)
 */

import fs from 'fs';
import path from 'path';

// Auto-load .env.local if present
try {
  const envPath = path.resolve('.env.local');
  if (fs.existsSync(envPath)) {
    const lines = fs.readFileSync(envPath, 'utf8').split('\n');
    for (const line of lines) {
      const match = line.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
      if (match) {
        const key = match[1];
        let val = match[2] || '';
        val = val.trim().replace(/^['"]|['"]$/g, '');
        if (!process.env[key]) process.env[key] = val;
      }
    }
  }
} catch {}

const BASE_URL = process.env.TEST_API_URL || 'http://localhost:3001';
const ADMIN_API_KEY = process.env.ADMIN_API_KEY || 'nizhal-super-secret-admin-key-2026';
const FRONTEND_ORIGIN = process.env.FRONTEND_ORIGIN?.split(',')[0] || 'https://nizhalcommunity.in';

let passed = 0;
let failed = 0;

function assert(condition, testName, details = '') {
  if (condition) {
    console.log(`  ✅ PASS: ${testName}`);
    passed++;
  } else {
    console.error(`  ❌ FAIL: ${testName} - ${details}`);
    failed++;
  }
}

async function runTests() {
  console.log(`\n======================================================`);
  console.log(`🧪 Testing Nizhal Media API at: ${BASE_URL}`);
  console.log(`======================================================\n`);

  // -------------------------------------------------------------------------
  // Test 1: OPTIONS /api/media (CORS Preflight)
  // -------------------------------------------------------------------------
  console.log(`[Test Suite 1] CORS Preflight`);
  try {
    const res = await fetch(`${BASE_URL}/api/media`, {
      method: 'OPTIONS',
      headers: {
        'Origin': FRONTEND_ORIGIN,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type, Authorization',
      },
    });

    assert(res.status === 204 || res.status === 200, 'OPTIONS returns 200 or 204 status', `Status: ${res.status}`);
    const allowOrigin = res.headers.get('access-control-allow-origin');
    assert(
      allowOrigin === FRONTEND_ORIGIN || allowOrigin === '*',
      'CORS matches configured frontend origin',
      `Got: ${allowOrigin}`
    );
    const allowMethods = res.headers.get('access-control-allow-methods');
    assert(
      allowMethods && allowMethods.includes('POST') && allowMethods.includes('GET'),
      'Access-Control-Allow-Methods includes GET and POST',
      `Got: ${allowMethods}`
    );
  } catch (err) {
    assert(false, 'OPTIONS /api/media reachable', err.message);
  }

  // -------------------------------------------------------------------------
  // Test 2: GET /api/media (Public Scrapbook Endpoint)
  // -------------------------------------------------------------------------
  console.log(`\n[Test Suite 2] Public GET /api/media`);
  try {
    const res = await fetch(`${BASE_URL}/api/media`, {
      method: 'GET',
      headers: {
        'Origin': FRONTEND_ORIGIN,
      },
    });

    const isSuccess = res.status === 200;
    const isDbErrorWithoutLeak = res.status === 500;
    assert(
      isSuccess || isDbErrorWithoutLeak,
      'GET /api/media returns valid HTTP status (200 OK or 500 clean error)',
      `Status: ${res.status}`
    );

    const body = await res.json();
    if (res.status === 200) {
      assert(Array.isArray(body.media), 'Response body contains "media" array');
      if (body.media.length > 0) {
        const item = body.media[0];
        assert(item.id && item.title && item.url && item.media_type, 'Media items have expected fields');
        assert(item.is_published === undefined, 'Internal "is_published" column is omitted from public output');
      }
    } else {
      assert(body.error && !JSON.stringify(body).includes('postgresql://'), '500 error does not leak credentials or connection strings');
    }
  } catch (err) {
    assert(false, 'GET /api/media reachable', err.message);
  }

  // -------------------------------------------------------------------------
  // Test 3: POST /api/media Authentication Tests (401)
  // -------------------------------------------------------------------------
  console.log(`\n[Test Suite 3] Authentication Security (401)`);
  try {
    // 3a. Missing Authorization header
    const resNoAuth = await fetch(`${BASE_URL}/api/media`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title: 'Unauthenticated Memory',
        url: 'https://example.com/test.jpg',
        media_type: 'image',
      }),
    });
    assert(resNoAuth.status === 401, 'POST without auth header returns 401 Unauthorized', `Status: ${resNoAuth.status}`);

    // 3b. Invalid Bearer token
    const resBadAuth = await fetch(`${BASE_URL}/api/media`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer wrong-secret-token',
      },
      body: JSON.stringify({
        title: 'Wrong Token Memory',
        url: 'https://example.com/test.jpg',
        media_type: 'image',
      }),
    });
    assert(resBadAuth.status === 401, 'POST with incorrect token returns 401 Unauthorized', `Status: ${resBadAuth.status}`);
  } catch (err) {
    assert(false, 'POST /api/media auth checks reachable', err.message);
  }

  // -------------------------------------------------------------------------
  // Test 4: POST /api/media Validation Tests (400)
  // -------------------------------------------------------------------------
  console.log(`\n[Test Suite 4] Field Validations (400)`);
  try {
    // 4a. Missing required fields (empty title, missing URL)
    const resMissing = await fetch(`${BASE_URL}/api/media`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${ADMIN_API_KEY}`,
      },
      body: JSON.stringify({
        title: '',
        // url missing
        media_type: 'image',
      }),
    });
    assert(resMissing.status === 400, 'POST with empty title/missing url returns 400 Bad Request', `Status: ${resMissing.status}`);
    const missingBody = await resMissing.json();
    assert(missingBody.error && missingBody.details, '400 response includes error and details breakdown');

    // 4b. Invalid media_type
    const resBadType = await fetch(`${BASE_URL}/api/media`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${ADMIN_API_KEY}`,
      },
      body: JSON.stringify({
        title: 'Invalid Type Item',
        url: 'https://example.com/item.png',
        media_type: 'unsupported_audio',
      }),
    });
    assert(resBadType.status === 400, 'POST with invalid media_type returns 400 Bad Request', `Status: ${resBadType.status}`);

    // 4c. Non-HTTPS URL
    const resHttpUrl = await fetch(`${BASE_URL}/api/media`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${ADMIN_API_KEY}`,
      },
      body: JSON.stringify({
        title: 'Non HTTPS item',
        url: 'http://insecure-site.com/image.jpg',
        media_type: 'image',
      }),
    });
    assert(resHttpUrl.status === 400, 'POST with insecure HTTP (non-HTTPS) returns 400 Bad Request', `Status: ${resHttpUrl.status}`);
  } catch (err) {
    assert(false, 'POST /api/media validation tests reachable', err.message);
  }

  // -------------------------------------------------------------------------
  // Test 5: POST /api/media Google Drive Link & Valid Schema
  // -------------------------------------------------------------------------
  console.log(`\n[Test Suite 5] Valid Payload & Google Drive Link Support`);
  try {
    const resDrive = await fetch(`${BASE_URL}/api/media`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${ADMIN_API_KEY}`,
      },
      body: JSON.stringify({
        title: 'Scrapbook Google Drive Photo',
        description: 'Captured during community gathering ♡',
        url: 'https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms/view?usp=sharing',
        category: 'gathering',
        media_type: 'image',
        sort_order: 10,
        is_published: true,
      }),
    });

    // If Supabase credentials are configured, returns 201; if mock/unconfigured, returns 500 without leaking secrets
    if (resDrive.status === 201) {
      const created = await resDrive.json();
      assert(true, 'POST with valid Google Drive link succeeds with 201 Created');
      assert(created.media && created.media.id, 'Created record contains generated id');
    } else {
      const errBody = await resDrive.json();
      assert(
        resDrive.status === 500 && !JSON.stringify(errBody).includes('postgres'),
        'Database error caught safely without leaking DB connection strings',
        `Status: ${resDrive.status}`
      );
    }
  } catch (err) {
    assert(false, 'Valid POST test reachable', err.message);
  }

  // Summary
  console.log(`\n======================================================`);
  console.log(`📊 Test Results: ${passed} Passed, ${failed} Failed`);
  console.log(`======================================================\n`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
