# url-shortener

Two services : 
- url-service
- redirect-service

We have separate services, so the reads can scale differently from the writes. 
URL shortening is a read-heavy service, so the redirects need to be scaled differently, the url creation (write) traffic is much smaller. 


1. For ```url-service``` - 
A client requests their original url to be shortened. 
The url-service checks the DB if the original url has been created, if yes -> returns the shortUrl. 
Otherwise, it creates the shortUrl, stores it in the DB and returns it to the user.

2. For ```redirect-service``` - 
A client clicks on the shortUrl, the server checks the DB for the shortCode.
If the shortCode is present and not expired, the server sends a 302 redirect (temporary redirect) to the originalUrl.

Otherwise, the server sends back a url not found error.

PRODUCT-DECISIONS:
1. For Original URL (with deterministic code):
If mapping exists and is active:
  return existing shortUrl

If mapping exists and is expired:
  reactivate same shortCode
  update expiration_time from request
    provided expirationTime -> use it
    no expirationTime -> set None forever
  return same shortUrl

If mapping does not exist:
  create mapping
  expiration_time = request expirationTime or None
  return shortUrl

2. For Alias:
If alias exists and is active:
  reject with 409 Conflict

If alias exists and is expired:
  reuse alias for the new request
  update original_url
  keep short_code = alias
  update expiration_time from request
  return alias shortUrl

If alias does not exist:
  create mapping with short_code = alias
  alias = alias
  expiration_time = request expirationTime or None
  return alias shortUrl


DEEP-DIVES:
Creating a short url by the url-service, has consequences. If the shortUrl creation is deterministic (i.e. an original url will always convert to the same shortCode/shortUrl), then we can always FIRST create the shortUrl, then check the DB, then return the result. This would be things like : hashing + base62 encoding. 

If the method is non-deterministic, like random number generator, there are two options :
1. Create the shortUrl, then check for collision in DB, store in DB. -> This leads to multiple shortUrls for the same originalUrl. 
2. Read the DB for existing originalUrl, if not existing create the shortUrl, store in DB, return to user. -> This results in a single shortUrl for an originalUrl.

Due to the heavy read of non-deterministic approaches, we stick to deterministic approach. 
In which case, we first create the shortUrl, then check the DB for the same, and then return to the user.
<Can improve for scalability>.

Approaches for creating short code:
1. Hashing + base63 encoding - Take a hash function like SHA256 which given an input, produces deterministic fixed-size string of characters. We then base62 encode it and take the first N characters as the short code.

How to choose N?
We need to generate 1B urls. 1B = 10^9. Base62 encoding gives us 62 characters. So we want 
62^N > 10^9.
N = 5, is just under 1B.
So we can take N=6 ~56B.

Reason for base62 encoding - Compact representation of a-z, A-Z, 0-9. IT excludes +, /, etc as that is a slash operator in URLs and + can be interpreterd as a space in query strings.

2. Counter with hashing - Incremeent a counter for a new URL, encode using base62. This ensures the URL is always uniqe and no collisions. Still have to read the DB for checking if the URL has been created before, but no need to read for collisions.