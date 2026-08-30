"""add decrypt_aes256cbc_base64 function

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-30 15:20:00.000000

"""
from alembic import op


revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
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
          raw := decode(input_text, 'base64');

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
    op.execute("DROP FUNCTION IF EXISTS public.decrypt_aes256cbc_base64(text);")
