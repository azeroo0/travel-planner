# 어디갈건호 프론트

## DB 장소 목록

`/admin/places`는 현재 DB의 전체 장소 목록을 읽기 전용으로 표시합니다(스크랩 목록은 `/scraps`). 프론트 서버(Next.js)에서만 PostgreSQL에 접속하며, 브라우저에는 비밀번호가 전달되지 않습니다. 로컬 실행 시 `backend/.env`의 `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`를 사용합니다. 백엔드 코드나 API 명세서는 변경하지 않습니다.

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:3000/admin/places`에서 목록을 확인하세요. 현재 DB의 `places.place_name`이 모두 비어 있어 장소 ID와 원본 ID를 표시합니다. 장소 상세·추천·분석 API 연결은 이후 작업입니다. 메인 로그인 화면은 연결 전 표시용입니다.
