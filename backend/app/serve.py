"""Production entry point. One worker keeps analysis admission limits global."""

import os

import uvicorn


def main():
    uvicorn.run(
        'app.main:app', host='0.0.0.0', port=int(os.getenv('PORT', '10000')),
        workers=1, limit_concurrency=32, timeout_keep_alive=5,
        timeout_graceful_shutdown=55, server_header=False,
        # App behavior does not depend on user-supplied forwarding headers.
        proxy_headers=False,
    )


if __name__ == '__main__':
    main()
