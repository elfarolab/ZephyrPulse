// R2 bucket remains private. The Worker exposes only the active release's files.
export default {
  async fetch(request, env) {
    if (!['GET', 'HEAD'].includes(request.method)) return new Response('Method not allowed', {status: 405, headers: {Allow: 'GET, HEAD'}});
    const current = await env.SITE.get('current.json');
    if (!current) return new Response('No release published', {status: 503});
    const {release} = await current.json();
    if (!/^[\w-]+$/.test(release)) return new Response('Invalid release', {status: 503});
    let path;
    try { path = decodeURIComponent(new URL(request.url).pathname).replace(/^\/+/, ''); }
    catch { return new Response('Bad path', {status: 400}); }
    if (path.split('/').some(s => s === '..' || s === '.') || path.includes('\\')) return new Response('Bad path', {status: 400});
    if (!path || path.endsWith('/')) path += 'index.html';
    const object = await env.SITE.get(`releases/${release}/${path}`);
    if (!object) return new Response('Not found', {status: 404});
    const headers = new Headers();
    object.writeHttpMetadata(headers);
    headers.set('ETag', object.httpEtag);
    headers.set('Cache-Control', 'no-store');
    headers.set('X-Content-Type-Options', 'nosniff');
    if (request.headers.get('If-None-Match') === object.httpEtag) return new Response(null, {status: 304, headers});
    return new Response(request.method === 'HEAD' ? null : object.body, {headers});
  }
};
