======================
 Review bot for GitHub
======================

This github bot posts review of pull-requests with odoo modules: list of updated files (installable and non-installable), new features to test (according to doc/changelog.rst file)

Create AWS Lambda function
--------------------------

`Create lambda function <https://console.aws.amazon.com/lambda/>`__ with following settings:

* Runtime

  Use ``Python 3.6``

* Environment variables

  * ``GITHUB_TOKEN`` -- generate one in https://github.com/settings/tokens . Select scope ``repo``.
  * ``LOG_LEVEL`` -- optional. Set to DEBUG to get detailed logs in AWS CloudWatch.

* Trigger

  Use ``API Gateway``. Once you configure it and save, you will see ``API endpoint`` under Api Gateway **details** section. Use option ``Open``

  Now register the URL as webhook at github: https://developer.github.com/webhooks/creating/.
  Use following webhook settings:

  * **Payload URL** -- the URL
  * **Content Type**: application/json
  * **Which events would you like to trigger this webhook?** -- *Let me select individual events* and then select ``[x] Pull request``

* Function Code

  * Use this commands:

    .. code-block:: console

        mkdir /tmp/github-review-bot
        cd /tmp/github-review-bot

        pip3 install pyGithub -t .
        wget https://gitlab.com/itpp/odoo-devops/raw/master/tools/github-review-bot/lambda_function.py
        wget https://gitlab.com/itpp/odoo-devops/raw/master/tools/github-review-bot/text_tree.py
        zip -r /tmp/github-review-bot.zip *

  * Then set **Code Entry type** to ``Upload a .zip file`` and select the created zip file
* Basic settings

  * Change time running function to 50 sec -- ``Timeout`` (default 3 sec)

Logs
----

* AWS CloudWatch: https://console.aws.amazon.com/cloudwatch . Choose tab ``Logs``

Roadmap
-------

* TODO: Deleted files should be listed with tag ``[DELETED]``
* TODO: Renamed files should be listed with tag ``[RENAMED from path/to/original-file]`` (for new files) and ``[RENAMED]`` (for original place of the file)
* TODO: New modules (e.g. root ``__init__.py`` didn't exist) should be marked with tag ``[NEW]``, e.g. ``├─ [NEW] pos_debt_notebook/``
* TODO: Ported modules (``installable`` attribute is changed from False to True)  should be marked with tag ``[PORT]``, e.g. ``├─ [PORT] pos_debt_notebook/``
* Updating review doesn't work without write access to the repo: github API returns 404. See https://gitlab.com/itpp/odoo-devops/issues/3