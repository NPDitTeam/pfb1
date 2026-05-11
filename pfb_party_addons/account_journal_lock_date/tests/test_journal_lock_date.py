# Copyright 2017 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date, timedelta

from odoo.exceptions import UserError

from odoo.addons.account.tests import common


class TestJournalLockDate(common.AccountTestInvoicingCommon):
    def setUp(self):
        super(TestJournalLockDate, self).setUp()
        self.account_move_obj = self.env["account.move"]
        self.account_move_line_obj = self.env["account.move.line"]
        self.company_id = self.ref("base.main_company")
        self.partner = self.browse_ref("base.res_partner_12")

        self.account = self.company_data["default_account_revenue"]
        self.account2 = self.company_data["default_account_expense"]
        self.journal = self.company_data["default_journal_bank"]

    def test_journal_lock_date_adviser(self):
        """ The journal lock date is ignored for Advisers """
        self.env.user.write(
            {"groups_id": [(4, self.env.ref("account.group_account_manager").id)]}
        )
        self.assertTrue(self.env.user.has_group("account.group_account_manager"))
        # create a move and post it
        move = self.account_move_obj.create(
            {
                "date": date.today(),
                "journal_id": self.journal.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.account.id,
                            "credit": 1000.0,
                            "name": "Credit line",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": self.account2.id,
                            "debit": 1000.0,
                            "name": "Debit line",
                        },
                    ),
                ],
            }
        )
        move.action_post()
        # lock journal. Set 'Lock Date'
        self.journal.fiscalyear_lock_date = date.today() + timedelta(days=2)
        # lock journal. Set 'Lock Date for Non-Advisers'
        self.journal.period_lock_date = date.today() + timedelta(days=4)
        # Advisers cannot create, write, or cancel moves before 'Lock Date'
        with self.assertRaises(UserError):
            self.account_move_obj.create(
                {
                    "date": date.today(),
                    "journal_id": self.journal.id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "account_id": self.account.id,
                                "credit": 1000.0,
                                "name": "Credit line",
                            },
                        ),
                        (
                            0,
                            0,
                            {
                                "account_id": self.account2.id,
                                "debit": 1000.0,
                                "name": "Debit line",
                            },
                        ),
                    ],
                }
            )
        with self.assertRaises(UserError):
            move.write({"name": "TEST"})

        with self.assertRaises(UserError):
            move.button_cancel()
        # Advisers can create movements on a date after the 'Lock Date'
        # even if that date is before and inclusive of
        # the 'Lock Date for Non-Advisers' (self.journal.period_lock_date)
        move3 = self.account_move_obj.create(
            {
                "date": self.journal.period_lock_date,
                "journal_id": self.journal.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.account.id,
                            "credit": 1000.0,
                            "name": "Credit line",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": self.account2.id,
                            "debit": 1000.0,
                            "name": "Debit line",
                        },
                    ),
                ],
            }
        )
        move3.action_post()
