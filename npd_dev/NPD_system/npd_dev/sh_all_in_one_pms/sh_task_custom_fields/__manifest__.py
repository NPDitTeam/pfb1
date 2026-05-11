# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name": "Task Custom Fields",
    
    "author": "Softhealer Technologies",
    
    "website": "https://www.softhealer.com",    
    
    "support": "support@softhealer.com",   

    "version": "13.0.3",
    
    "category": "Extra Tools",
    
    "summary": """
	  Add  Task New Field Module, Make Task Dynamic Fields, Create Task New Field App, Assign Custom Fields Odoo. Edit/UpdateTask Custom Field Odoo.

	""",
        
	 "description": """
	This module useful to create dynamic fields in the task without any technical knowledge. Easy to use. Specify basic things and fields added in the form view.
 Task Custom Fields Odoo, Task Dynamic Field Odoo.
  Add New Field In Task Form View Module, Create Dynamic Field In Task, Feature For Add Multiple Fields In Task Odoo.
  Add  Task New Field Module, Make Task Dynamic Fields, Create Task New Field App, Assign Custom Fields Odoo. Edit/UpdateTask Custom Field Odoo.


	""",
     
    "depends": ['project'],
        
    "data": [
        "data/task_custom_field_group.xml",
        "security/ir.model.access.csv",
        "views/task.xml", 
        "views/task_tab.xml",     
    ],    
    
    "images": ["static/description/background.png",],             
    
    "installable": True,    
    "auto_install": False,    
    "application": True,    
    
    "price": "35",    
    "currency": "EUR"     
}
