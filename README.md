# psycopg-vcrlike

Something like pyvcr and python-recording, but for recording SQL queries.

I love [pytest-recording](https://github.com/kiwicom/pytest-recording),
but I need to also cache my (read-only, async) SQL queries.
This is a quick-and-dirty extension of the same VCR practice to async psycopg.
The vast majority of the functionality isn't mocked properly.

Current:
* not all asynchronous API is covered
* the synchronous part is not covered at all
* read-only, expects same requests to yield same results
