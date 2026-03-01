const token = localStorage.getItem('token');
if (!token) window.location.href = '/login.html';

let map;
let fogLayer = null;
let isUpdatingFog = false;

let isBrushActive = false;
let isDrawing = false;
let currentLine = null;
let currentCoords =[];

async function authFetch(url, options = {}) {
    if (!options.headers) options.headers = {};
    if (!(options.body instanceof FormData) && !options.headers['Content-Type']) {
        options.headers['Content-Type'] = 'application/json';
    }
    options.headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(url, options);
    if (res.status === 401) {
        localStorage.removeItem('token');
        window.location.href = '/login.html';
    }
    return res;
}

async function initMap() {
    let lat = 55.751244, lng = 37.618423, zoom = 5;

    try {
        const vpRes = await authFetch('/api/viewport');
        if (vpRes.ok) {
            let vp = await vpRes.json();
            if (typeof vp === 'string') vp = JSON.parse(vp);
            if (vp && vp.lat) { lat = vp.lat; lng = vp.lng; zoom = vp.zoom; }
        }
    } catch(e) { console.warn("Viewport пуст, берем дефолт"); }

    map = L.map('map', { attributionControl: false }).setView([lat, lng], zoom);
    L.tileLayer('https://tile{s}.maps.2gis.com/tiles?x={x}&y={y}&z={z}&v=1', {
        subdomains: ['0', '1', '2', '3'],
        maxZoom: 18
    }).addTo(map);

    map.pm.addControls({
        position: 'topleft', drawCircle: false, drawCircleMarker: false,
        drawMarker: false, drawPolyline: false, drawRectangle: true,
        drawPolygon: true, editMode: false, dragMode: false, removalMode: false
    });

    map.on('pm:create', async (e) => {
        const geojson = e.layer.toGeoJSON();
        map.removeLayer(e.layer);
        sendDrawData(geojson.geometry);
    });

    map.on('moveend', () => {
        const center = map.getCenter();
        authFetch('/api/viewport', {
            method: 'POST',
            body: JSON.stringify({ lat: center.lat, lng: center.lng, zoom: map.getZoom() })
        });
        updateFog();
    });

    setupPaintBrush();
    updateFog();
}

function setupPaintBrush() {
    const btnBrush = document.getElementById('btn-brush');

    btnBrush.addEventListener('click', () => {
        isBrushActive = !isBrushActive;
        if (isBrushActive) {
            btnBrush.innerText = '🖌 Режим Paint: ВКЛ';
            btnBrush.style.backgroundColor = '#28a745';
            map.dragging.disable();
            map.getContainer().style.cursor = 'crosshair';
        } else {
            btnBrush.innerText = '🖌 Режим Paint: ВЫКЛ';
            btnBrush.style.backgroundColor = '#ff9800';
            map.dragging.enable();
            map.getContainer().style.cursor = '';
        }
    });

    map.on('mousedown', (e) => {
        if (!isBrushActive) return;
        isDrawing = true;
        currentCoords = [[e.latlng.lng, e.latlng.lat] ];
        currentLine = L.polyline([e.latlng], {color: 'white', weight: 15, opacity: 0.5}).addTo(map);
    });

    map.on('mousemove', (e) => {
        if (!isDrawing) return;
        currentCoords.push([e.latlng.lng, e.latlng.lat]);
        currentLine.addLatLng(e.latlng);
    });

    map.on('mouseup', () => {
        if (!isDrawing) return;
        isDrawing = false;

        if (currentCoords.length > 1) {
            const geojson = { type: "LineString", coordinates: currentCoords };
            map.removeLayer(currentLine);
            sendDrawData(geojson);
        } else if (currentLine) {
            map.removeLayer(currentLine);
        }
    });
}

async function sendDrawData(geometry) {
    try {
        const res = await authFetch('/api/draw', {
            method: 'POST', body: JSON.stringify(geometry)
        });
        if (!res.ok) throw new Error(await res.text());
        updateFog();
    } catch (err) {
        alert('Ошибка рисования: ' + err.message);
    }
}

async function updateFog() {
    if (isUpdatingFog) return;
    isUpdatingFog = true;
    try {
        const bounds = map.getBounds();
        const res = await authFetch(`/api/fog?minx=${bounds.getWest()}&miny=${bounds.getSouth()}&maxx=${bounds.getEast()}&maxy=${bounds.getNorth()}`);
        if (!res.ok) throw new Error("Ошибка тумана");
        const fogGeoJSON = await res.json();

        if (fogLayer) map.removeLayer(fogLayer);
        fogLayer = L.geoJSON(fogGeoJSON, {
            style: { color: '#111', fillColor: '#111', fillOpacity: 0.45, weight: 0, interactive: false }
        }).addTo(map);
    } catch (e) { console.error(e); }
    finally { isUpdatingFog = false; }
}

document.getElementById('gpx-file').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    const btn = document.getElementById('btn-upload');
    const originalText = btn.innerText;
    btn.innerText = '⏳ Загрузка...';
    btn.disabled = true;

    try {
        const res = await authFetch('/api/upload-gpx', { method: 'POST', body: formData });
        if (!res.ok) throw new Error("Ошибка при обработке GPX");
        updateFog();
    } catch (err) { alert(err.message); }
    finally { btn.innerText = originalText; btn.disabled = false; e.target.value = ''; }
});

document.getElementById('btn-undo').addEventListener('click', async () => {
    try {
        const res = await authFetch('/api/draw/undo', { method: 'POST' });
        if (!res.ok) throw new Error("Не удалось отменить");
        updateFog();
    } catch (err) { alert(err.message); }
});

document.getElementById('btn-logout').addEventListener('click', () => {
    localStorage.removeItem('token');
    window.location.href = '/login.html';
});

initMap();