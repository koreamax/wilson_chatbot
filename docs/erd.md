# Wilson ERD v1 (Phase 0)

> BE(Spring Boot·PostgreSQL) 데이터 모델. BE RDBMS = 원본(실 PII). **AI엔 가명 `subject_id`만** 흘러가고, `turn_id`가 gRPC 대화 ↔ Kafka 인지지표의 조인 키다.
> 연구 보관·삭제 정책은 [research-retention.md](research-retention.md) 참조.

```mermaid
erDiagram
    RESEARCH_SUBJECT ||--o| ELDER : "가명(철회시 링크 절단)"
    ELDER            ||--o{ GUARDIAN_ELDER : ""
    GUARDIAN         ||--o{ GUARDIAN_ELDER : ""
    ELDER            ||--o{ CONSENT : ""
    GUARDIAN         ||--o{ CONSENT : "granted_by(대리동의)"
    ELDER            ||--o{ SESSION : ""
    SESSION          ||--o{ TURN : ""
    TURN             ||--o| COGNITIVE_METRIC : "turn_id (1:0..1)"
    RESEARCH_SUBJECT ||--o{ COGNITIVE_METRIC : "보관 키"
    ELDER            ||--o{ ELDER_BASELINE : ""
    ELDER            ||--o{ ASSESSMENT_FLAG : ""
    ELDER            ||--o{ GUARDIAN_INSIGHT : ""
    GUARDIAN         ||--o{ GUARDIAN_INSIGHT : "열람"
    GUARDIAN         ||--o{ NOTIFICATION : ""

    RESEARCH_SUBJECT {
        uuid subject_id PK "AI로 가는 target_user_id"
        timestamp created_at
        timestamp withdrawn_at "nullable"
    }
    ELDER {
        uuid elder_id PK "내부, 철회시 파기"
        uuid subject_id FK
        string login_id
        string pw_hash
        string name "PII"
        date birth_date "PII"
        timestamp created_at
    }
    GUARDIAN {
        uuid guardian_id PK
        string login_id
        string pw_hash
        string name "PII"
        string phone "PII"
        timestamp created_at
    }
    GUARDIAN_ELDER {
        uuid id PK
        uuid guardian_id FK
        uuid elder_id FK
        string relationship "딸/아들/배우자"
        string role "OWNER|MEMBER"
        string status "PENDING|ACTIVE"
        string legal_basis "성년후견/가족위임/기타"
        timestamp created_at
    }
    CONSENT {
        uuid consent_id PK
        uuid elder_id FK
        uuid granted_by FK "guardian_id"
        string consent_type "민감정보|일반"
        bool research_retention_agreed
        int version
        timestamp granted_at
        timestamp revoked_at "nullable=철회"
    }
    SESSION {
        uuid session_id PK
        uuid elder_id FK
        timestamp started_at
        timestamp ended_at
        string status
    }
    TURN {
        uuid turn_id PK "gRPC/Kafka 조인 키, BE 생성"
        uuid session_id FK
        uuid elder_id FK
        int seq
        text stt_text "ENC, 철회시 파기"
        text llm_response_text "ENC, 철회시 파기"
        timestamp created_at
    }
    COGNITIVE_METRIC {
        uuid id PK
        uuid turn_id UK "turn 1:0..1, 멱등"
        uuid subject_id FK "가명 보관 키"
        bool analyzable
        int morpheme_token_count
        int utterance_count
        float filler_ratio
        float empty_speech_ratio
        float content_info_unit_ratio
        float words_per_utterance
        float subsequent_onset_latency_ms
        float silent_pause_ratio
        float jitter
        float shimmer
        float cpp
        jsonb neural "TBD"
        jsonb emotion "TBD"
        timestamp analyzed_at
    }
    ELDER_BASELINE {
        uuid id PK
        uuid elder_id FK
        string metric
        float moving_avg
        float std
        timestamp updated_at
    }
    ASSESSMENT_FLAG {
        uuid id PK
        uuid elder_id FK
        string metric_type
        bool flag
        float cutoff_applied
        int window_days
        timestamp computed_at
    }
    GUARDIAN_INSIGHT {
        uuid id PK
        uuid elder_id FK
        uuid guardian_id FK
        string type "불평/상태변화"
        text content "요약(원문 아님)"
        string period
        timestamp created_at
    }
    NOTIFICATION {
        uuid id PK
        uuid guardian_id FK
        string type
        text payload
        timestamp sent_at
        timestamp read_at "nullable"
    }
```

## 엔티티 요약 & 보관 정책

| 엔티티 | 역할 | 철회 시 |
|---|---|---|
| **research_subject** | 연구용 가명 키. AI `target_user_id` = 이 값 | **보관** (링크만 절단) |
| **elder / guardian** | 계정(각자 로그인) + PII | elder **파기** |
| **guardian_elder** | N:M 관계 + 권한. OWNER/MEMBER·PENDING/ACTIVE, 첫 링크=OWNER, 이후 OWNER 승인 | **파기** |
| **consent** | 민감정보 대리동의(보호자 근거), 연구보관 동의 | **파기** |
| **session / turn** | 대화 원본(STT+LLM). turn 텍스트 ENC | **파기** |
| **cognitive_metric** | 턴 단위 인지지표(수치). turn_id UNIQUE(멱등), neural/emotion JSONB | **보관** (subject_id) |
| **elder_baseline** | 개인별 동적 baseline(cut-off 상대판정용) | 파기 |
| **assessment_flag** | BE 누적·N일 연속 판정 결과 | 파기 |
| **guardian_insight** | elder→guardian 가공본(원문 노출 금지) | 파기 |
| **notification** | 보호자 푸시 | 파기 |

## 핵심 설계 결정 (요약)
1. **두-tier 신원**: `research_subject`(가명, 보관) ↔ `elder`(PII, 파기). AI는 subject_id만.
2. **N:M + 승인**: guardian_elder role/status, 첫 보호자=OWNER, 이후 OWNER 승인. 마지막 OWNER unlink 금지(소유권 이전 강제) + 고아 시 유예 후 파기.
3. **대리동의 법적 근거**: consent.granted_by + legal_basis. 유효성은 [자문 필요].
4. **조인 키**: turn_id(BE 생성) — 대화·지표 조인. metric은 turn 1:0..1 + turn_id UNIQUE(Kafka 멱등).
5. **암호화**: turn 텍스트 at-rest 암호화(MVP: 볼륨/TDE → 후에 컬럼암호화 승격).
6. **삭제/보관**: 철회 = PII·원문·임베딩·매핑 cascade 파기, 지표는 subject_id로 가명 보관(연구·통계, PIPA 가명정보 특례). rolling-window(M)은 ChromaDB 캐시 정리(별개).
