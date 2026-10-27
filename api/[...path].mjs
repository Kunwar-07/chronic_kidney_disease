import {loadConfig} from '../backend/src/config.mjs';
import {loadRegistry} from '../backend/src/models.mjs';
import {createApp} from '../backend/src/app.mjs';

let serverPromise;

async function getServer() {
  if (!serverPromise) {
    const config = loadConfig({
      ...process.env,
      HOST: '127.0.0.1',
      PORT: '8000',
      MODEL_DATA_DIR: process.env.MODEL_DATA_DIR || undefined,
    });
    serverPromise = loadRegistry(config.dataDir).then(registry => createApp({config, registry}));
  }
  return serverPromise;
}

export default async function handler(request, response) {
  try {
    const server = await getServer();
    const listener = server.listeners('request')[0];
    await listener(request, response);
  } catch (error) {
    if (!response.headersSent) {
      response.statusCode = 500;
      response.setHeader('Content-Type', 'application/json; charset=utf-8');
      response.end(JSON.stringify({
        status: 'error',
        error: {code: 'startup_error', message: 'The API could not start.'},
      }));
    }
    console.error(`Vercel API startup failed: ${error.message}`);
  }
}
