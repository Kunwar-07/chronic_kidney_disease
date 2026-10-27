import {loadConfig} from './config.mjs';
import {loadRegistry} from './models.mjs';
import {createApp} from './app.mjs';

try {
  const config = loadConfig();
  const registry = await loadRegistry(config.dataDir);
  const server = createApp({config, registry});
  server.on('error', error => {
    console.error(`Backend server error: ${error.code || 'UNKNOWN'}`);
    process.exitCode = 1;
  });
  server.listen(config.port, config.host, () => {
    console.log(`Nephra API listening on http://${config.host}:${config.port}`);
    console.log('API documentation: /openapi.json');
  });
  let stopping = false;
  const stop = () => {
    if (stopping) return;
    stopping = true;
    const deadline = setTimeout(() => server.closeAllConnections(), 10000);
    deadline.unref();
    server.close(() => clearTimeout(deadline));
  };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
} catch (error) {
  console.error(`Backend startup failed: ${error.message}`);
  process.exitCode = 1;
}
