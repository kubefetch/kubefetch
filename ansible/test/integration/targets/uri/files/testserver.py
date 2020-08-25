import sys

if __name__ == '__main__':
    if sys.version_info[0] >= 3:
        import http.server
        import socketserver
        PORT = int(sys.argv[1])

        class Handler(http.server.SimpleHTTPRequestHandler):
            pass

        Handler.extensions_map['.json'] = 'application/json'
        httpd = socketserver.TCPServer(("", PORT), Handler)
        httpd.serve_forever()
    else:
        import mimetypes
        mimetypes.init()
        mimetypes.add_type('application/json', '.json')
        import SimpleHTTPServer
        SimpleHTTPServer.test()
