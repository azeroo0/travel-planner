// The API specification has no free-text chat endpoint.
// Kept only to give old callers an explicit error instead of fabricated recommendations.
export async function POST() {
  return Response.json(
    { error: { code: 'UNSUPPORTED_ENDPOINT', message: '추천은 GET /api/recommendations를 사용해 주세요.' } },
    { status: 410 },
  );
}
