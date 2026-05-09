import { getLightStreak, getCurvedStreak } from '../src/streak';
import type { PathSampler } from '../src/streak';

// Straight line streak
const straight = getLightStreak({ x: 0, y: 0 }, { x: 200, y: 100 }, 0.5);
console.log('Straight streak:', straight);

// Curved streak along a quadratic arc
const arc: PathSampler = (t) => ({
  x: t * 200,
  y: 100 - Math.sin(t * Math.PI) * 50,
});

const curved = getCurvedStreak(arc, 0.5, 0.2, 8);
console.log('Curved streak:', curved);

// Streak at different progress values
for (const p of [0.1, 0.3, 0.5, 0.7, 0.9]) {
  const s = getCurvedStreak(arc, p, 0.15, 6);
  console.log(`Progress ${p}:`, s);
}
