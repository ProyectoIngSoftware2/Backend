-- =====================================================================
-- Sprint 2 - Idempotent test-admin seed for the auth layer (Phase 2).
--
-- TEST CREDENTIALS (test environment only, never real users):
--   correo:    admin.prueba@puntoysal.test
--   password:  AdminPys2026!
--
-- The stored hash below is a real bcrypt hash (cost 12) generated with
-- the repository's bcrypt library; the plaintext above exists only in
-- this comment and is needed so the team can log in during Sprint 2.
--
-- SAFETY / IDEMPOTENCY:
--   * INSERT guarded by WHERE NOT EXISTS (natural key: correo).
--   * UPDATE guarded so it is a no-op once the bcrypt hash is in place
--     (re-running changes 0 rows).
--   * Depends on sprint2_auth_schema.sql having been applied first.
--   * STATUS: written in Phase 2 but NOT executed yet - running it
--     requires explicit team approval (writes to NeonDB are gated).
-- =====================================================================

-- 1) Insert the test administrator's login account if it does not exist.
INSERT INTO public.usuarios (correo, password_hash, rol, activo)
SELECT 'admin.prueba@puntoysal.test',
       '$2b$12$dwYG7iZ65XWEKSP./ImRN.9bEpgudHgi6kFTWbfed9dAsBOCjr/Vu',
       'administrador',
       true
WHERE NOT EXISTS (
    SELECT 1 FROM public.usuarios WHERE correo = 'admin.prueba@puntoysal.test'
);

-- 2) Repair the password if a non-bcrypt placeholder sneaked into the
--    usuarios row (no-op once the real bcrypt hash is stored).
UPDATE public.usuarios
SET password_hash = '$2b$12$dwYG7iZ65XWEKSP./ImRN.9bEpgudHgi6kFTWbfed9dAsBOCjr/Vu'
WHERE correo = 'admin.prueba@puntoysal.test'
  AND password_hash NOT LIKE '$2%';

-- 3) Replace the Sprint 1 placeholder in the legacy administradores
--    column with the same bcrypt hash (keeps both columns consistent).
--    No-op after the first run.
UPDATE public.administradores
SET password_hash = '$2b$12$dwYG7iZ65XWEKSP./ImRN.9bEpgudHgi6kFTWbfed9dAsBOCjr/Vu'
WHERE correo = 'admin.prueba@puntoysal.test'
  AND password_hash = 'PLACEHOLDER_SPRINT2_WILL_HASH_THIS';

-- 4) Link the administradores profile to its usuario row (1:1, nullable
--    while the account is being created). No-op after the first run.
UPDATE public.administradores a
SET id_usuario = u.id_usuario
FROM public.usuarios u
WHERE a.correo = 'admin.prueba@puntoysal.test'
  AND u.correo = 'admin.prueba@puntoysal.test'
  AND a.id_usuario IS NULL;

-- Verification (read-only):
--   SELECT u.id_usuario, u.correo, u.rol, u.activo,
--          (u.password_hash LIKE '$2%') AS has_bcrypt_hash,
--          a.id_administrador, a.id_usuario AS linked_id_usuario
--   FROM public.usuarios u
--   LEFT JOIN public.administradores a ON a.id_usuario = u.id_usuario
--   WHERE u.correo = 'admin.prueba@puntoysal.test';
