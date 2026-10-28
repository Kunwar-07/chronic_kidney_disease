import fs from 'node:fs/promises';
import path from 'node:path';
const root = path.resolve(import.meta.dirname, '..'), dist = path.join(root, 'dist');
await fs.mkdir(dist, {recursive:true});
for (const name of ['index.html','styles.css','app.mjs','assessment.mjs','research.mjs','charts.mjs','ui.mjs','motion.mjs','assets','data']) {
  await fs.cp(path.join(root, name), path.join(dist, name), {recursive:true});
}
const report = JSON.parse(await fs.readFile(path.join(dist, 'data/report.json')));
console.log(`Static build verified: ${report.version}, ${Object.keys(report.tasks).length} pathways. Output: ${dist}`);
