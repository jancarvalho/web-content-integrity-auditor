# =============================================================================
# Project: Web Content Integrity Auditor (WCIA)
#
# Original Author: Jânio Ribeiro
# Role: Senior Data QA Engineer & Data Engineer
#
# Copyright (c) 2026 Jânio Ribeiro
#
# SPDX-License-Identifier: MIT
#
# Description:
# An asynchronous framework for website discovery,
# content integrity validation, and audit reconciliation.
#
# Originally designed and developed by Jânio Ribeiro.
# =============================================================================
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0].rstrip('/')
        status = 200
        if path == '/section':
            content = '''<div id="results"></div><button id="more">Show More</button><script>
let i=0; function add(){ for(let n=0;n<10 && i<40;n++,i++){let a=document.createElement('a');a.href='/section/guides/article-'+i;a.textContent='Article '+i;document.querySelector('#results').append(a,document.createElement('br'));}if(i===40)document.querySelector('#more').remove();}document.querySelector('#more').onclick=()=>setTimeout(add,300);add();</script>'''
        elif path == '/section/guides':
            content = 'Guide index'
        elif path.startswith('/section/guides/article-'):
            n = int(path.rsplit('-',1)[1]); content = '' if n==0 else 'Short article' if n==1 else 'Detailed article content describes a sample topic. '*10
            if n==2: status=503
        else:
            status=404; content='Not found'
        body=f'<!doctype html><html><head><title>Example content</title></head><body><header>Example header</header><nav><a href="/outside">Outside</a></nav><main>{content}</main><footer>Example footer</footer></body></html>'.encode()
        self.send_response(status); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(body)

if __name__=='__main__': ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
