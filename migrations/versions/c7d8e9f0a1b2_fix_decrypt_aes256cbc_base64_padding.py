"""fix decrypt_aes256cbc_base64 base64 padding

Revision ID: c7d8e9f0a1b2
Revises: c6d7e8f9a0b1
Create Date: 2026-08-30 15:35:00.000000

"""
from alembic import op


revision = "c7d8e9f0a1b2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.decrypt_aes256cbc_base64(input_text text)
        RETURNS text
        LANGUAGE plpgsql
        IMMUTABLE
        AS $function$
        DECLARE
          normalized_text text;
          raw bytea;
          iv bytea;
          data bytea;
        BEGIN
          IF input_text IS NULL OR input_text = '' THEN
            RETURN NULL;
          END IF;

          -- PostgreSQL の decode は標準 Base64 のみ対応。URL-safe (-, _) を変換し、パディングを補完する
          normalized_text := regexp_replace(replace(replace(input_text, '-', '+'), '_', '/'), '\\s', '', 'g');
          normalized_text := normalized_text || repeat('=', (4 - length(normalized_text) % 4) % 4);
          raw := decode(normalized_text, 'base64');

          iv := substring(raw from 1 for 16);

          data := substring(raw from 17);

          RETURN convert_from(
            decrypt_iv(
              data,
              '0123456789abcdef0123456789abcdef'::bytea,
              iv,
              'aes'
            ),
            'UTF8'
          );
        END;
        $function$
        """
    )


def downgrade():
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.decrypt_aes256cbc_base64(input_text text)
        RETURNS text
        LANGUAGE plpgsql
        IMMUTABLE
        AS $function$
        DECLARE
          raw bytea;
          iv bytea;
          data bytea;
        BEGIN
          IF input_text IS NULL OR input_text = '' THEN
            RETURN NULL;
          END IF;

          raw := decode(
            regexp_replace(replace(replace(input_text, '-', '+'), '_', '/'), '\\s', '', 'g'),
            'base64'
          );

          iv := substring(raw from 1 for 16);

          data := substring(raw from 17);

          RETURN convert_from(
            decrypt_iv(
              data,
              '0123456789abcdef0123456789abcdef'::bytea,
              iv,
              'aes'
            ),
            'UTF8'
          );
        END;
        $function$
        """
    )
