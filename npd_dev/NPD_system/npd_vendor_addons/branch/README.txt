
Version 14.0.0.1 : (23/10/20)
		- Update _assign_picking() and _create_account_move_line() methods as per base.

14.0.0.3==> added abstract_web_client js according to v14.

=> 14.0.0.4 : Add language translate with index.


date 03/05/21
version 14.0.0.5
issue solve:-
	- invoice and bill genenrated in sinlge click

=> 14.0.0.9 : Add French, Spanish , Arabic and Dutch translation in module also improved an index.


date 02/09/21
version 14.0.1.0
issue solve:-
	- account payment register wizard not show branch field.

date 09/09/21
version 14.0.2.0
issue solve:-
	- show branch field in sale , purchase ,invoice bill and payment tree view

date 13/09/21
version 14.0.3.0
issue solve:-
1. From demo user->In sale rights, I give  User: Own Documents Only ->but it shows the sale order of all the users(when I give branch in sale order)

2. From demo user, ->change branch from header ->in pos, when I open shop it generates traceback

3. from demo user->in Invoice -> It shows all the invoices of all the branches.

date 27/09/21
version 14.0.4.0
issue solve:-
1.) . Sales -> Quotation / Orders -> On changing Branch from dropdown header it shows older branch records until refresh the page. Not refreshing records with changing branch.


14.0.4.1 (1-10-21) : Pass branch in account move correct, two view name same for different object changed it and fixed.

14.0.4.2 (20-01-22) : Fixed the xpath issue in account payment form view


date 25th feb 2022
version 14.0.4.3
improve code:-
	- change field position where its resolve issue while issue in web_studio

14.0.4.4 ==>fixed issue of traceback for record rules when uninstall module.
14.0.4.5==>assigned automatically "Branch/Manager" access to Administrator user after module installed and when create new user as  it's works for all other apps i.e purchase, sale, pos etc 


date 1st july 2022
version 14.0.4.6
issue solve:-
	=> call super in session_info method

14.0.4.7 ==>fixed issue of changed write method of res user in upgraded addons.

14.0.4.8 ==>fixed issue of branch assign by company.