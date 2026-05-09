import { generateGridDots, gridPatternCss } from '../src/canvas_grid_pattern';

const camera = { panX: 0, panY: 0, zoom: 1, viewportWidth: 800, viewportHeight: 600 };

// Generate dots
const dots = generateGridDots(camera);
console.log(`Dots at zoom=1: ${dots.length}`);
console.log('First 3:', dots.slice(0, 3));

// Zoomed out (dots fade, fewer dots)
const zoomedOut = generateGridDots({ ...camera, zoom: 0.3 });
console.log(`Dots at zoom=0.3: ${zoomedOut.length}, opacity=${zoomedOut[0]?.opacity}`);

// CSS approach (more performant)
const css = gridPatternCss(camera);
console.log('CSS:', JSON.stringify(css, null, 2));

// Custom styling
const customCss = gridPatternCss(camera, {
  baseSpacing: 30,
  dotRadius: 1.5,
  dotColor: '#c0c0c0',
});
console.log('Custom CSS:', JSON.stringify(customCss, null, 2));
