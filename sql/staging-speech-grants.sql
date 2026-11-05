


BEGIN;
GRANT EXECUTE ON FUNCTION public.reserve_meeting_speech(uuid,uuid,uuid,bigint,uuid[],text,integer,integer) TO aedrova_website;
GRANT EXECUTE ON FUNCTION public.finish_meeting_speech(uuid,uuid,text) TO aedrova_website;
COMMIT;
