import { ViewportCameraStore } from '../src/viewport_camera_store';

const cam = new ViewportCameraStore({ initialZoom: 1 });
cam.setViewport(1920, 1080);

// Subscribe to changes
cam.subscribe(state => {
  console.log(`Camera: pan(${state.panX.toFixed(1)}, ${state.panY.toFixed(1)}) zoom=${state.zoom.toFixed(2)}`);
});

// Pan the camera
cam.pan(100, 50);

// Zoom toward center of screen
cam.zoomAt(960, 540, 1.5);

// Convert coordinates
const world = cam.screenToWorld(960, 540);
console.log(`Center of screen in world: (${world.x.toFixed(1)}, ${world.y.toFixed(1)})`);

const screen = cam.worldToScreen(world.x, world.y);
console.log(`Back to screen: (${screen.x.toFixed(1)}, ${screen.y.toFixed(1)})`);

// Get viewport bounds
const bounds = cam.getViewportBounds();
console.log(`Viewport bounds: ${JSON.stringify(bounds)}`);

// Fit to a world rectangle
cam.fitBounds({ x: 0, y: 0, width: 500, height: 400 });
console.log(`After fitBounds: zoom=${cam.getState().zoom.toFixed(2)}`);
