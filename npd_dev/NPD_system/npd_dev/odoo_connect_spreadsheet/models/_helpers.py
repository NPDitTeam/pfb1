"""
Some of the helpers below are sourced from: https://python.plainenglish.io/master-google-sheets-api-in-python-cheat-sheet-3535e86fbe17
"""
from googleapiclient import discovery
from google.oauth2 import service_account


def google_drive_authentication(scopes, service_account_json_credentials):
    """
    Authentication to the Google Drive API

    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/spreadsheets"
    ]

    service_account_json_credentials = {
        "type": "service_account",
        "project_id": "odoo-spreadsheet-371808",
        "private_key_id": "75b6f5a2caff78examplef122742d907",
        "private_key": "-----BEGIN PRIVATE KEY-----\example\nZQDD7Kj8Ql/example+75QeTHK95B6gBoeoHDIWnoLGK9mEq6NG2\naZRAhZyEpIYYaxakQ74Q21O8a6k4DV/sjoAToaT+AUrGhuZYmBQa1aTgJrjuC7vX\nKlYvn0orC44lUKicXbIjDoCavOq0ZE6m4IsAqkawXW/U1iNgV3K6PV6+example\n167wVaDmEND5VC7QISTja9rpbGMI8OU6/example+FoJyqrUywk5iFRm4example+IutJCyEJ3AW4LmsYrBNbA\example/t0QnivKHonXhdNYqU9kmSkm8dL3wpJe86Gg3K\ngRUrZOuH02ESvR4HcMJlqYj7jXu0AmL1xrUGNqTGuGTR5M4qPUYwx/+VZFqb5DBZ\n2U7Eib2Kiw7k0v/McPlc1nYSVwtWqf8rgoTCZltbhdSI+HpfxNeWPJan2RUln7tD\nQd79kZz793V1Egat3RC7k2w1FMboEzPNtXLK3J/mQeUvYIzmtsdOGO1c0phelmuv\nu6M9a1HaPLzAR1DxGqUZRE1OpFAPkI72FUL2by0KN3O2tQzS5kMA6u5VikvBiyyV\nphDfv9o0o5EwITjL50w4cOniTh2TtkUKphZXXV+UwQKBgQDjrwXYdxmJls/oO9Hk\nshMGyUJ4+P/syMJtylNCHgb+jUKsfPPjWGzK5EvE68cMHGcrTdjceOElPs+xkE+Q\nix/sA6OJrPOvyfR/Mo87uGkK7kjs8/DbxNlCtMc2zI6oyZyFHZMgMHFjMEFRy4Lg\nkRSFXqZeqhMB45wN/DNJyL4hqQKBgQDSBHWanW46924Cf5pR4kILDMHODN3Tt1st\nJt8DQrNI2k/eXz2nPB9tSXQyDdzJqr0XqwJIaWVQqfuBC6c9JopgNDS9v3/le94k\nOicGAqV/rlPnhrOLU71rhSb0cExTzuG/rZnFHb6bqGxomebizi8tI9jIhvCJVM4w\ntXH1cIWSQQKBgQC+wdjn74EZ4Zz3OYc1UGzYdq6WpCfnvpwHWEhBUN8TTk7aLSY5\nB9C+fF9u8QunffSCN4rFzRD1H5brcbj3pVhtaO8PXjQcx9ts5nNS2cJIQjQfMpJN\nzrMoTEXMB75Oc/wLGyg1A+E79SYE3bkdZPAIfbBuB5g9MPGCVhaybtm9YQKBgE51\nEgYv1/U5aCSQzPLYJroACwrR7bDhJ7OneNq7+UQ3Im09gUfPgyINtdXZLek82qVT\n4mdw0EOhLO7ZjqGem0UzW5yjRMFTU/qOqvNo27DmTDwLK1nab8ISHSpmJW2NtPIp\nhW+JHCMEeXNeQ03pnuArKxpGpud3AgxaTHdXkN7BAoGBAMGRuJaevHjn5gQ5U6Tw\nr9SNQ2CFneknoZIp6VsuP6sWWXkGFrFYD3gDwJdI5DQ9lukvb+jpENx36put7Xpf\nVKMk2DAB7hlIQzJaK8tjwrnaaC3+mOIEsoGpI5h+BIK13/VhAafF99WnuTZb9s39\nRUlhcCFJQVfTW1Jaj5ds95l6\n-----END PRIVATE KEY-----\n",
        "client_email": "odoo12@odoo-spreadsheet-example-371808.iam.gserviceaccount.com",
        "client_id": "101569074example",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/odoo12%40odoo-spreadsheet-example.iam.gserviceaccount.com"
    }
    """

    credentials = service_account.Credentials.from_service_account_info(service_account_json_credentials, scopes=scopes)
    drive_service = discovery.build('drive', 'v3', credentials=credentials)
    return drive_service


def google_sheet_authentication(scopes, service_account_json_credentials):
    """
    Authentication to the Google Sheet API

    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/spreadsheets"
    ]

    service_account_json_credentials = {
        "type": "service_account",
        "project_id": "odoo-spreadsheet-371808",
        "private_key_id": "75b6f5a2caff78examplef122742d907",
        "private_key": "-----BEGIN PRIVATE KEY-----\example\nZQDD7Kj8Ql/example+75QeTHK95B6gBoeoHDIWnoLGK9mEq6NG2\naZRAhZyEpIYYaxakQ74Q21O8a6k4DV/sjoAToaT+AUrGhuZYmBQa1aTgJrjuC7vX\nKlYvn0orC44lUKicXbIjDoCavOq0ZE6m4IsAqkawXW/U1iNgV3K6PV6+example\n167wVaDmEND5VC7QISTja9rpbGMI8OU6/example+FoJyqrUywk5iFRm4example+IutJCyEJ3AW4LmsYrBNbA\example/t0QnivKHonXhdNYqU9kmSkm8dL3wpJe86Gg3K\ngRUrZOuH02ESvR4HcMJlqYj7jXu0AmL1xrUGNqTGuGTR5M4qPUYwx/+VZFqb5DBZ\n2U7Eib2Kiw7k0v/McPlc1nYSVwtWqf8rgoTCZltbhdSI+HpfxNeWPJan2RUln7tD\nQd79kZz793V1Egat3RC7k2w1FMboEzPNtXLK3J/mQeUvYIzmtsdOGO1c0phelmuv\nu6M9a1HaPLzAR1DxGqUZRE1OpFAPkI72FUL2by0KN3O2tQzS5kMA6u5VikvBiyyV\nphDfv9o0o5EwITjL50w4cOniTh2TtkUKphZXXV+UwQKBgQDjrwXYdxmJls/oO9Hk\nshMGyUJ4+P/syMJtylNCHgb+jUKsfPPjWGzK5EvE68cMHGcrTdjceOElPs+xkE+Q\nix/sA6OJrPOvyfR/Mo87uGkK7kjs8/DbxNlCtMc2zI6oyZyFHZMgMHFjMEFRy4Lg\nkRSFXqZeqhMB45wN/DNJyL4hqQKBgQDSBHWanW46924Cf5pR4kILDMHODN3Tt1st\nJt8DQrNI2k/eXz2nPB9tSXQyDdzJqr0XqwJIaWVQqfuBC6c9JopgNDS9v3/le94k\nOicGAqV/rlPnhrOLU71rhSb0cExTzuG/rZnFHb6bqGxomebizi8tI9jIhvCJVM4w\ntXH1cIWSQQKBgQC+wdjn74EZ4Zz3OYc1UGzYdq6WpCfnvpwHWEhBUN8TTk7aLSY5\nB9C+fF9u8QunffSCN4rFzRD1H5brcbj3pVhtaO8PXjQcx9ts5nNS2cJIQjQfMpJN\nzrMoTEXMB75Oc/wLGyg1A+E79SYE3bkdZPAIfbBuB5g9MPGCVhaybtm9YQKBgE51\nEgYv1/U5aCSQzPLYJroACwrR7bDhJ7OneNq7+UQ3Im09gUfPgyINtdXZLek82qVT\n4mdw0EOhLO7ZjqGem0UzW5yjRMFTU/qOqvNo27DmTDwLK1nab8ISHSpmJW2NtPIp\nhW+JHCMEeXNeQ03pnuArKxpGpud3AgxaTHdXkN7BAoGBAMGRuJaevHjn5gQ5U6Tw\nr9SNQ2CFneknoZIp6VsuP6sWWXkGFrFYD3gDwJdI5DQ9lukvb+jpENx36put7Xpf\nVKMk2DAB7hlIQzJaK8tjwrnaaC3+mOIEsoGpI5h+BIK13/VhAafF99WnuTZb9s39\nRUlhcCFJQVfTW1Jaj5ds95l6\n-----END PRIVATE KEY-----\n",
        "client_email": "odoo12@odoo-spreadsheet-example-371808.iam.gserviceaccount.com",
        "client_id": "101569074example",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/odoo12%40odoo-spreadsheet-example.iam.gserviceaccount.com"
    }
    """

    credentials = service_account.Credentials.from_service_account_info(service_account_json_credentials, scopes=scopes)
    spreadsheet_service = discovery.build('sheets', 'v4', credentials=credentials)
    return spreadsheet_service


def create_drive_folder(drive_service, folder_name):
    """
    Create a Drive Folder

    file_metadata = {
        'name': 'medium_spreadsheet_folder',
        'mimeType': 'application/vnd.google-apps.folder'
    }
    """
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    file = drive_service.files().create(body=file_metadata, fields='id').execute()
    folder_id = file.get('id')
    return folder_id


def update_folder_permission(drive_service, folder_id, email_address):
    """
    Update folder permissions

    new_permissions = {
        'type': 'group',
        'role': 'writer',
        'emailAddress': EMAIL_ADDRESS
    }
    """

    new_permissions = {
        'type': 'group',
        'role': 'writer',
        'emailAddress': email_address
    }  # todo | should we loop it to update multiple users and permissions?

    permission_response = drive_service.permissions().create(
        fileId=folder_id, body=new_permissions).execute()

    return permission_response


def create_spreadsheet(spreadsheet_service, spreadsheet_title):
    """
    Create a spreadsheet

    spreadsheet = {
        'properties': {
            'title': "medium_spreadsheet_file"
        }
    }
    """
    spreadsheet = {
        'properties': {
            'title': spreadsheet_title
        }
    }
    creation_response = spreadsheet_service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()

    spreadsheet_id = creation_response.get('spreadsheetId')
    return spreadsheet_id


def update_spreadsheet(spreadsheet_service, spreadsheet_id, range_name, _values):
    """
    Update a spreadsheet

    range_name = "A1:C2"
    If the number of rows is variable, you can use this value in range_name :
    range_name = "A1:C{}".format(len(rows))

    values = [
        ["Medium Channel", "Views", "Likes"],
        ["Beranger", "'{}".format(10983908), '{}'.format(13084)]
    ]
    """

    data = {'values': _values}

    update_response = spreadsheet_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        body=data,
        range=range_name,
        valueInputOption='USER_ENTERED').execute()

    return update_response


def read_value_from_spreadsheet(spreadsheet_service, spreadsheet_id, range_name):
    """
    Read values from a spreadsheet

    range_name = "Sheet1!A1:C2"
    """
    response = spreadsheet_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()

    return response['values']


def update_spreadsheet_permission(drive_service, spreadsheet_id, type, role, email_address):
    """
    new_file_permission = {
        'type': 'group',
        'role': 'writer',
        'emailAddress': trinanda_example_email@gmail.com
    }
    """
    new_file_permission = {
        'type': type,
        'role': role,
        'emailAddress': email_address,
    }

    permission_response = drive_service.permissions().create(
        fileId=spreadsheet_id, body=new_file_permission).execute()

    return permission_response


def move_folder(drive_service, spreadsheet_id, folder_id):
    """
    Move to folder
    The previous update_spreadsheet_permission method is great if you have only a few spreadsheets to grant access to.
    But if you plan to create a huge number of spreadsheets, you will receive a huge number of email, You should
    instead use this method. We won’t update spreadsheet’s permissions but we will move the spreadsheet into a
    folder that already have the wanted permissions.
    Remember the folder we created using create_drive_folder method? We simply use his folder_id and the spreadsheet’s
    permissions will be automatically updated.
    """
    get_parents_response = drive_service.files().get(fileId=spreadsheet_id, fields='parents').execute()
    previous_parents = ",".join(get_parents_response.get('parents'))
    move_response = drive_service.files().update(fileId=spreadsheet_id, addParents=folder_id,
                                                 removeParents=previous_parents, fields='id, parents').execute()
    return move_response


def add_sheet(spreadsheet_service, spreadsheet_id, sheet_name):
    # Create a AddSheetRequest object:
    add_sheet_request = {
        "addSheet": {
            "properties": {
                "title": sheet_name
            }
        }
    }

    # Create a BatchUpdateSpreadsheetRequest object:
    request = {
        "requests": [add_sheet_request]
    }

    response = spreadsheet_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=request).execute()
    return response


def spreadsheet_metadata(spreadsheet_service, spreadsheet_id):
    response = spreadsheet_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return response


def clear_spreadsheet_data(spreadsheet_service, spreadsheet_id, range_name):
    # Call the spreadsheets.values.clear method:
    result = spreadsheet_service.spreadsheets().values().clear(spreadsheetId=spreadsheet_id, range=range_name).execute()
    return result


def append_values(spreadsheet_service, spreadsheet_id, range_name, _values, insert_data_option, major_dimension):
    """Append values to spreadsheet"""
    data = {'values': _values, 'majorDimension': major_dimension}
    result = spreadsheet_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption='USER_ENTERED', insertDataOption=insert_data_option,
        body=data).execute()
    return result
