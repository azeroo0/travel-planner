import 'server-only';

import { Pool } from 'pg';
import { config } from 'dotenv';
import { resolve } from 'node:path';

config({ path: resolve(process.cwd(), '../backend/.env'), override: false, quiet: true });

const globalForDb = globalThis as typeof globalThis & { __placePool?: Pool };

function pool(): Pool {
  if (!process.env.POSTGRES_HOST || !process.env.POSTGRES_DB || !process.env.POSTGRES_USER) {
    throw new Error('DB 접속 설정이 없습니다. backend/.env 또는 프론트 서버 환경 변수를 확인하세요.');
  }
  return globalForDb.__placePool ??= new Pool({
    host: process.env.POSTGRES_HOST,
    port: Number(process.env.POSTGRES_PORT || 5432),
    database: process.env.POSTGRES_DB,
    user: process.env.POSTGRES_USER,
    password: process.env.POSTGRES_PASSWORD,
    max: 3,
    connectionTimeoutMillis: 5000,
    idleTimeoutMillis: 10000,
  });
}

export type DbPlace = {
  place_id: number;
  source_place_id: string;
  place_name: string | null;
  category_code: string;
  review_count: number;
};

export async function listDbPlaces(page: number): Promise<{ items: DbPlace[]; total: number }> {
  const db = pool();
  const [list, count] = await Promise.all([
    db.query<DbPlace>(
      `SELECT p.place_id, p.source_place_id, p.place_name, c.category_code,
              COUNT(r.review_id)::int AS review_count
       FROM places p
       JOIN place_categories c ON c.category_id = p.category_id
       LEFT JOIN reviews r ON r.place_id = p.place_id
       GROUP BY p.place_id, p.source_place_id, p.place_name, c.category_code
       ORDER BY p.place_id
       LIMIT $1 OFFSET $2`,
      [20, (page - 1) * 20],
    ),
    db.query<{ total: string }>('SELECT COUNT(*) AS total FROM places'),
  ]);
  return { items: list.rows, total: Number(count.rows[0].total) };
}
