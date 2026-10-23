/**
 * IRM — inquiry form endpoint (Cloudflare Pages Function)
 * POST /api/inquiry  (multipart/form-data from the site's inquiry form)
 *
 * Creates a Lead in Zoho CRM and attaches any uploaded files.
 *
 * Environment variables (Cloudflare Pages → Settings → Environment variables, encrypted):
 *   ZOHO_CLIENT_ID       OAuth client ID (Zoho API Console, "Self Client" or server-based app)
 *   ZOHO_CLIENT_SECRET   OAuth client secret
 *   ZOHO_REFRESH_TOKEN   refresh token with scopes ZohoCRM.modules.leads.CREATE, ZohoCRM.modules.attachments.CREATE
 *   ZOHO_ACCOUNTS_URL    optional, default https://accounts.zoho.com (use .eu/.in etc. for other data centers)
 *   ZOHO_API_URL         optional, default https://www.zohoapis.com
 *   ZOHO_LEAD_SOURCE     optional, a value that exists in the Leads "Lead Source" picklist (e.g. "Website")
 *   ZOHO_OWNER_ID        optional, Zoho user id to own new leads
 *   TURNSTILE_SECRET     optional, enables Cloudflare Turnstile verification
 *
 * Responds with JSON when the request sends "Accept: application/json" (the site's script does);
 * otherwise redirects to /contact/thanks/ so the form also works without JavaScript.
 */

const MAX_FILES = 5;
const MAX_TOTAL_BYTES = 10 * 1024 * 1024;
const ALLOWED_TYPES = /^(image\/(jpeg|png|webp|heic|heif)|application\/pdf)$/i;
const FIELD_LIMITS = { name: 120, company: 160, email: 160, phone: 60, country: 80, inquiry_type: 40, material: 200, quantity: 120, message: 5000, lang: 8, source_page: 200 };

let cachedToken = null; // { token, expires } — reused within a warm isolate

function clean(value, max) {
  return String(value || "").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "").trim().slice(0, max);
}

function respond(request, status, body) {
  const wantsJson = (request.headers.get("Accept") || "").includes("application/json");
  if (wantsJson) {
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
  }
  if (body.ok) return Response.redirect(new URL("/contact/thanks/", request.url).toString(), 303);
  const msg = body.error === "files"
    ? "Attachments are too large or of an unsupported type. Please email them to info@irmllc.co."
    : "Your inquiry could not be sent. Please email info@irmllc.co.";
  return new Response(`<!doctype html><meta charset="utf-8"><title>IRM</title><p>${msg}</p><p><a href="/contact/">Back</a></p>`, { status, headers: { "Content-Type": "text/html; charset=utf-8" } });
}

async function verifyTurnstile(env, token, ip) {
  if (!env.TURNSTILE_SECRET) return true;
  if (!token) return false;
  const form = new FormData();
  form.append("secret", env.TURNSTILE_SECRET);
  form.append("response", token);
  if (ip) form.append("remoteip", ip);
  const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form });
  const j = await r.json().catch(() => ({}));
  return j.success === true;
}

async function zohoToken(env) {
  if (cachedToken && cachedToken.expires > Date.now() + 60_000) return cachedToken.token;
  const base = env.ZOHO_ACCOUNTS_URL || "https://accounts.zoho.com";
  const params = new URLSearchParams({
    refresh_token: env.ZOHO_REFRESH_TOKEN,
    client_id: env.ZOHO_CLIENT_ID,
    client_secret: env.ZOHO_CLIENT_SECRET,
    grant_type: "refresh_token",
  });
  const r = await fetch(`${base}/oauth/v2/token`, { method: "POST", body: params });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.access_token) throw new Error("zoho_token");
  cachedToken = { token: j.access_token, expires: Date.now() + (Number(j.expires_in) || 3600) * 1000 };
  return cachedToken.token;
}

export async function onRequestPost({ request, env }) {
  let data;
  try {
    data = await request.formData();
  } catch {
    return respond(request, 400, { ok: false, error: "bad_request" });
  }

  // Honeypot: real visitors never fill this field. Pretend success to bots.
  if (clean(data.get("website"), 200)) return respond(request, 200, { ok: true });

  const f = {};
  for (const [key, max] of Object.entries(FIELD_LIMITS)) f[key] = clean(data.get(key), max);

  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email);
  if (!f.name || !emailOk || !f.message || data.get("consent") !== "yes") {
    return respond(request, 422, { ok: false, error: "required" });
  }

  const ip = request.headers.get("CF-Connecting-IP") || "";
  if (!(await verifyTurnstile(env, data.get("cf-turnstile-response"), ip))) {
    return respond(request, 403, { ok: false, error: "verification" });
  }

  const files = data.getAll("files").filter((x) => x && typeof x === "object" && x.size > 0);
  const total = files.reduce((n, x) => n + x.size, 0);
  if (files.length > MAX_FILES || total > MAX_TOTAL_BYTES || files.some((x) => !ALLOWED_TYPES.test(x.type || ""))) {
    return respond(request, 413, { ok: false, error: "files" });
  }

  if (!env.ZOHO_CLIENT_ID || !env.ZOHO_CLIENT_SECRET || !env.ZOHO_REFRESH_TOKEN) {
    console.error("inquiry: Zoho credentials are not configured");
    return respond(request, 503, { ok: false, error: "not_configured" });
  }

  const parts = f.name.split(/\s+/);
  const lastName = parts.length > 1 ? parts.pop() : f.name;
  const firstName = parts.length ? parts.join(" ") : "";

  const description = [
    `Topic: ${f.inquiry_type || "—"}`,
    `Material: ${f.material || "—"}`,
    `Quantity: ${f.quantity || "—"}`,
    `Language: ${f.lang || "en"}`,
    `Page: ${f.source_page || "—"}`,
    `Attachments: ${files.length}`,
    "",
    f.message,
    "",
    `Consent to privacy notice: yes (${new Date().toISOString()})`,
  ].join("\n");

  const lead = {
    Last_Name: lastName,
    First_Name: firstName || undefined,
    Company: f.company || undefined,
    Email: f.email,
    Phone: f.phone || undefined,
    Country: f.country || undefined,
    Description: description,
    Lead_Status: "Not Contacted",
  };
  if (env.ZOHO_LEAD_SOURCE) lead.Lead_Source = env.ZOHO_LEAD_SOURCE;
  if (env.ZOHO_OWNER_ID) lead.Owner = { id: env.ZOHO_OWNER_ID };

  const api = env.ZOHO_API_URL || "https://www.zohoapis.com";
  try {
    const token = await zohoToken(env);
    const r = await fetch(`${api}/crm/v8/Leads`, {
      method: "POST",
      headers: { Authorization: `Zoho-oauthtoken ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ data: [lead], trigger: ["workflow"] }),
    });
    const j = await r.json().catch(() => ({}));
    const rec = j && j.data && j.data[0];
    if (!r.ok || !rec || rec.code !== "SUCCESS") {
      console.error("inquiry: lead create failed", r.status, JSON.stringify(j).slice(0, 500));
      return respond(request, 502, { ok: false, error: "crm" });
    }
    const leadId = rec.details && rec.details.id;

    // Attach files one by one; a failed attachment does not fail the inquiry.
    for (const file of files) {
      const body = new FormData();
      body.append("file", file, file.name || "attachment");
      const a = await fetch(`${api}/crm/v8/Leads/${leadId}/Attachments`, {
        method: "POST",
        headers: { Authorization: `Zoho-oauthtoken ${token}` },
        body,
      });
      if (!a.ok) console.error("inquiry: attachment failed", a.status, file.name);
    }
    return respond(request, 200, { ok: true });
  } catch (err) {
    console.error("inquiry: error", err && err.message);
    return respond(request, 502, { ok: false, error: "crm" });
  }
}

export function onRequest({ request }) {
  return new Response("Method not allowed", { status: 405, headers: { Allow: "POST" } });
}
