
import logging
import os
from flask import Flask, request
import schedule
import re
import json
import math
import proposal
import checklist
import internal_scope
import change_order

app = Flask(__name__, static_url_path='/static')
log = logging.getLogger('werkzeug')
log.disabled = True

app.add_url_rule('/proposal', view_func=proposal.make_proposal)
app.add_url_rule('/checklist', view_func=checklist.make_checklist)
app.add_url_rule('/internal-scope', view_func=internal_scope.make_internal_scope)
app.add_url_rule('/change-order', view_func=change_order.make_change_order)

@app.route("/check",methods=['GET'])
def health_check():
    return "CHECK WORKING"



def clean_static():
    count = 0
    for file in os.listdir('./static'):
        count += 1
        os.remove(file)

schedule.every().day.at("01:00").do(clean_static)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)