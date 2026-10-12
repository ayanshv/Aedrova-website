-- Run ONLY in Aedrova Staging, after the installed meeting speech migration.
-- The backend role was created after the migration, so its optional grants did not run.
-- No table access, service-role key, password or production change is requested.
BEGIN;
GRANT EXECUTE ON FUNCTION public.reserve_meeting_speech(uuid,uuid,uuid,bigint,uuid[],text,integer,integer) TO aedrova_website;
GRANT EXECUTE ON FUNCTION public.finish_meeting_speech(uuid,uuid,text) TO aedrova_website;
COMMIT;
