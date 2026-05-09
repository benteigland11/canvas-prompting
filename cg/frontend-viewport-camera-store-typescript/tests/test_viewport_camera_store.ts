import { ViewportCameraStore } from '../src/viewport_camera_store';

describe('ViewportCameraStore', () => {
  let cam: ViewportCameraStore;

  beforeEach(() => {
    cam = new ViewportCameraStore();
    cam.setViewport(800, 600);
  });

  test('default state', () => {
    const s = cam.getState();
    expect(s.panX).toBe(0);
    expect(s.panY).toBe(0);
    expect(s.zoom).toBe(1);
    expect(s.viewportWidth).toBe(800);
    expect(s.viewportHeight).toBe(600);
  });

  test('custom initial state', () => {
    const c = new ViewportCameraStore({ initialPanX: 100, initialPanY: 50, initialZoom: 2 });
    const s = c.getState();
    expect(s.panX).toBe(100);
    expect(s.panY).toBe(50);
    expect(s.zoom).toBe(2);
  });

  test('pan shifts offset', () => {
    cam.pan(10, -20);
    const s = cam.getState();
    expect(s.panX).toBe(10);
    expect(s.panY).toBe(-20);
  });

  test('pan accumulates', () => {
    cam.pan(10, 10);
    cam.pan(5, -3);
    const s = cam.getState();
    expect(s.panX).toBe(15);
    expect(s.panY).toBe(7);
  });

  test('setPan sets directly', () => {
    cam.setPan(100, 200);
    const s = cam.getState();
    expect(s.panX).toBe(100);
    expect(s.panY).toBe(200);
  });

  test('setZoom clamps to min', () => {
    cam.setZoom(0.01);
    expect(cam.getState().zoom).toBe(0.1);
  });

  test('setZoom clamps to max', () => {
    cam.setZoom(100);
    expect(cam.getState().zoom).toBe(5);
  });

  test('setZoom with custom bounds', () => {
    const c = new ViewportCameraStore({ minZoom: 0.5, maxZoom: 2 });
    c.setZoom(0.2);
    expect(c.getState().zoom).toBe(0.5);
    c.setZoom(3);
    expect(c.getState().zoom).toBe(2);
  });

  test('screenToWorld at zoom=1, pan=0', () => {
    const p = cam.screenToWorld(100, 200);
    expect(p.x).toBe(100);
    expect(p.y).toBe(200);
  });

  test('screenToWorld with pan', () => {
    cam.setPan(50, 100);
    const p = cam.screenToWorld(150, 200);
    expect(p.x).toBe(100);
    expect(p.y).toBe(100);
  });

  test('screenToWorld with zoom', () => {
    cam.setZoom(2);
    const p = cam.screenToWorld(200, 100);
    expect(p.x).toBe(100);
    expect(p.y).toBe(50);
  });

  test('worldToScreen is inverse of screenToWorld', () => {
    cam.setPan(30, -40);
    cam.setZoom(1.5);
    const world = cam.screenToWorld(250, 300);
    const screen = cam.worldToScreen(world.x, world.y);
    expect(screen.x).toBeCloseTo(250);
    expect(screen.y).toBeCloseTo(300);
  });

  test('getViewportBounds at zoom=1, pan=0', () => {
    const b = cam.getViewportBounds();
    expect(b.x).toBe(0);
    expect(b.y).toBe(0);
    expect(b.width).toBe(800);
    expect(b.height).toBe(600);
  });

  test('getViewportBounds with pan and zoom', () => {
    cam.setPan(-100, -50);
    cam.setZoom(2);
    const b = cam.getViewportBounds();
    expect(b.x).toBe(50);
    expect(b.y).toBe(25);
    expect(b.width).toBe(400);
    expect(b.height).toBe(300);
  });

  test('zoomAt keeps world point under cursor stable', () => {
    cam.setPan(0, 0);
    cam.setZoom(1);
    const worldBefore = cam.screenToWorld(400, 300);
    cam.zoomAt(400, 300, 2);
    const worldAfter = cam.screenToWorld(400, 300);
    expect(worldAfter.x).toBeCloseTo(worldBefore.x, 5);
    expect(worldAfter.y).toBeCloseTo(worldBefore.y, 5);
  });

  test('zoomAt no-op when already at max', () => {
    cam.setZoom(5);
    const before = cam.getState();
    cam.zoomAt(400, 300, 2);
    expect(cam.getState().zoom).toBe(before.zoom);
  });

  test('fitBounds centers and scales', () => {
    cam.fitBounds({ x: 100, y: 100, width: 200, height: 200 });
    const bounds = cam.getViewportBounds();
    const centerX = bounds.x + bounds.width / 2;
    const centerY = bounds.y + bounds.height / 2;
    expect(centerX).toBeCloseTo(200, 0);
    expect(centerY).toBeCloseTo(200, 0);
  });

  test('fitBounds respects zoom clamp', () => {
    cam.fitBounds({ x: 0, y: 0, width: 1, height: 1 });
    expect(cam.getState().zoom).toBeLessThanOrEqual(5);
  });

  test('fitBounds no-op with zero viewport', () => {
    const c = new ViewportCameraStore();
    const before = c.getState();
    c.fitBounds({ x: 0, y: 0, width: 100, height: 100 });
    expect(c.getState().zoom).toBe(before.zoom);
  });

  test('subscribe notifies on pan', () => {
    const spy = vi.fn();
    cam.subscribe(spy);
    cam.pan(10, 20);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0].panX).toBe(10);
  });

  test('subscribe notifies on setZoom', () => {
    const spy = vi.fn();
    cam.subscribe(spy);
    cam.setZoom(2);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  test('unsubscribe stops notifications', () => {
    const spy = vi.fn();
    const unsub = cam.subscribe(spy);
    unsub();
    cam.pan(10, 20);
    expect(spy).not.toHaveBeenCalled();
  });
});
