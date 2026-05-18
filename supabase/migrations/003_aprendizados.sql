-- ============================================================
-- Sprint 3: loop de aprendizado
-- ============================================================

-- rpm_previsto na sugestão (IA estima ao gerar)
alter table sugestoes add column if not exists rpm_previsto numeric(10,2);

-- tabela de aprendizados: 1 linha por vídeo publicado + vinculado
create table if not exists aprendizados (
  id            bigserial primary key,
  sugestao_id   uuid        references sugestoes(id) on delete set null,
  video_id      text        references videos(video_id) on delete set null,
  titulo_sugerido  text,
  titulo_publicado text,
  rpm_previsto  numeric(10,2) default 0,
  rpm_real      numeric(10,2) default 0,
  resultado     text check (resultado in ('acertou', 'parcial', 'errou', 'sem_dados')),
  analise_ia    text,
  created_at    timestamptz default now()
);

create index if not exists idx_aprendizados_sugestao on aprendizados(sugestao_id);
create index if not exists idx_aprendizados_created  on aprendizados(created_at desc);
