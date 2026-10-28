import {loadConfig} from '../src/config.mjs';
import {createSupabase} from '../src/supabase.mjs';

try {
  const database = createSupabase(loadConfig().supabase);
  if (!database) throw new Error('Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in backend/.env first.');
  const token = process.env.SUPABASE_TEST_ACCESS_TOKEN;
  if (!token) throw new Error('Set SUPABASE_TEST_ACCESS_TOKEN to a signed-in test user access token for this check.');
  const user = await database.authenticate(`Bearer ${token}`);
  await database.list(user, 1, 0);
  console.log('Supabase authentication and assessment table read succeeded. No data was written or displayed.');
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
