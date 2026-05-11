No Uninstall!!
If uninstall update database
update public.ir_module_module set state = 'installed' where name = 'l10n_th_tin_service';
And update module again
if use docker run
docker exec -it 83c5847a3132 psql -d greenpro -U odoo