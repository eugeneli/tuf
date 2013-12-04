"""
<Program Name>
  keys.py

<Author>
  Vladimir Diaz <vladimir.v.diaz@gmail.com>

<Started>
  October 4, 2013.

<Copyright>
  See LICENSE for licensing information.

<Purpose>
  The goal of this module is to centralize cryptographic key routines and their
  supported operations (e.g., creating and verifying signatures).  This module
  is designed to support multiple public-key algorithms, such as RSA and
  ED25519, and multiple cryptography libraries.  Which cryptography library to
  use is determined by the default, or user modified, values set in
  'tuf.conf.py'
  
  The (RSA and ED25519)-related functions provided include generate_rsa_key(),
  generate_ed5519_key(), create_signature(), and verify_signature().
  The cryptography libraries called by 'tuf.keys.py' generate the actual TUF
  keys and the functions listed above can be viewed as an easy-to-use public
  interface.
  
  Additional functions contained here include format_keyval_to_metadata() and
  format_metadata_to_key().  These last two functions produce or use TUF keys
  compatible with the key structures listed in TUF Metadata files.  The key
  generation functions return a dictionary containing all the information needed
  of TUF keys, such as public and private keys and a keyID.  create_signature()
  and verify_signature() are supplemental functions used for generating
  signatures and verifying them.
  
  https://en.wikipedia.org/wiki/RSA_(algorithm)
  http://ed25519.cr.yp.to/

  Key IDs are used as identifiers for keys (e.g., RSA key).  They are the
  hexadecimal representation of the hash of key object (specifically, the key
  object containing only the public key).  Review 'rsa_key.py' and the
  '_get_keyid()' function to see precisely how keyids are generated.  One may
  get the keyid of a key object by simply accessing the dictionary's 'keyid'
  key (i.e., rsakey['keyid']).
 """

# Required for hexadecimal conversions.  Signatures and public/private keys are
# hexlified.
import binascii

# 'pycrypto' is the only currently supported library for the creation of RSA
# keys.  https://github.com/dlitz/pycrypto
_SUPPORTED_RSA_CRYPTO_LIBRARIES = ['pycrypto']

# The currently supported libraries for the creation of ed25519 keys and
# signatures.  The 'pynacl' library should be installed and used over the slower
# python implementation of ed25519.  The python implementation will be used
# if 'pynacl' is unavailable.
_SUPPORTED_ED25519_CRYPTO_LIBRARIES = ['ed25519', 'pynacl']

# Track which libraries are imported and thus available.  A optimized version
# of the ed25519 python implementation is provided by TUF and avaialable by
# default.  https://github.com/pyca/ed25519
_available_crypto_libraries = ['ed25519']

# Import the PyCrypto library so that RSA keys are supported.
try:
  import Crypto
  import tuf.pycrypto_keys
  _available_crypto_libraries.append('pycrypto')
except ImportError:
  pass

# Import the PyNaCl library, if available.  It is recommended this library be
# used over the pure python implementation of ed25519, due to its speedier
# routines and side-channel protections available in the libsodium library.
try:
  import nacl
  _available_crypto_libraries.append('pynacl')
except ImportError:
  pass

# The optimized version of the ed25519 library provided by default is imported
# regardless of the availability of PyNaCl.
import tuf.ed25519_keys


# Import the TUF package and TUF-defined exceptions in __init__.py.
import tuf

# Import the cryptography library settings.
import tuf.conf

# Digest objects needed to generate hashes.
import tuf.hash

# Perform format checks of argument objects.
import tuf.formats

# The hash algorithm to use in the generation of keyids.
_KEY_ID_HASH_ALGORITHM = 'sha256'

# Recommended RSA key sizes:
# http://www.emc.com/emc-plus/rsa-labs/historical/twirl-and-rsa-key-size.htm#table1
# According to the document above, revised May 6, 2003, RSA keys of
# size 3072 provide security through 2031 and beyond.
_DEFAULT_RSA_KEY_BITS = 3072

# The crypto libraries to use in 'keys.py', set by default or by the user.
# The following cryptography libraries are currently supported:
# ['pycrypto', 'pynacl', 'ed25519']
_RSA_CRYPTO_LIBRARY = tuf.conf.RSA_CRYPTO_LIBRARY
_ED25519_CRYPTO_LIBRARY = tuf.conf.ED25519_CRYPTO_LIBRARY


def generate_rsa_key(bits=_DEFAULT_RSA_KEY_BITS):
  """
  <Purpose> 
    Generate public and private RSA keys, with modulus length 'bits'.  In
    addition, a keyid identifier for the RSA key is generated.  The object
    returned conforms to 'tuf.formats.RSAKEY_SCHEMA' and has the
    form:
    {'keytype': 'rsa',
     'keyid': keyid,
     'keyval': {'public': '-----BEGIN RSA PUBLIC KEY----- ...',
                'private': '-----BEGIN RSA PRIVATE KEY----- ...'}}
    
    The public and private keys are strings in PEM format.

    Although the PyCrypto crytography library called sets a 1024-bit minimum
    key size, generate() enforces a minimum key size of 2048 bits.  If 'bits' is
    unspecified, a 3072-bit RSA key is generated, which is the key size
    recommended by TUF. 
    
    >>> rsa_key = generate_rsa_key(bits=2048)
    >>> tuf.formats.RSAKEY_SCHEMA.matches(rsa_key)
    True
    >>> public = rsa_key['keyval']['public']
    >>> private = rsa_key['keyval']['private']
    >>> tuf.formats.PEMRSA_SCHEMA.matches(public)
    True
    >>> tuf.formats.PEMRSA_SCHEMA.matches(private)
    True
  
  <Arguments>
    bits:
      The key size, or key length, of the RSA key.  'bits' must be 2048, or
      greater, and a multiple of 256.

  <Exceptions>
    tuf.FormatError, if 'bits' is improperly or invalid (i.e., not an integer
    and not at least 2048).
   
    tuf.UnsupportedLibraryError, if any of the cryptography libraries specified
    in 'tuf.conf.py' are unsupported or unavailable.

    ValueError, if an exception occurs after calling the RSA key generation
    routine.  'bits' must be a multiple of 256.  The 'ValueError' exception is
    raised by the key generation function of the cryptography library called.

  <Side Effects>
    The RSA keys are generated by calling PyCrypto's
    Crypto.PublicKey.RSA.generate().

  <Returns>
    A dictionary containing the RSA keys and other identifying information.
    Conforms to 'tuf.formats.RSAKEY_SCHEMA'. 
  """

  # Does 'bits' have the correct format?
  # This check will ensure 'bits' conforms to 'tuf.formats.RSAKEYBITS_SCHEMA'.
  # 'bits' must be an integer object, with a minimum value of 2048.
  # Raise 'tuf.FormatError' if the check fails.
  tuf.formats.RSAKEYBITS_SCHEMA.check_match(bits)

  # Raise 'tuf.UnsupportedLibraryError' if the following libraries, specified in
  # 'tuf.conf', are unsupported or unavailable:
  # 'tuf.conf.RSA_CRYPTO_LIBRARY' and 'tuf.conf.ED25519_CRYPTO_LIBRARY'. 
  _check_crypto_libraries()

  # Begin building the RSA key dictionary. 
  rsakey_dict = {}
  keytype = 'rsa'
  public = None
  private = None

  # Generate the public and private RSA keys.  The PyCrypto module performs
  # the actual key generation.  Raise 'ValueError' if 'bits' is less than 1024 
  # or not a multiple of 256, although a 2048-bit minimum is enforced by
  # tuf.formats.RSAKEYBITS_SCHEMA.check_match().
  if _RSA_CRYPTO_LIBRARY == 'pycrypto':
    public, private = tuf.pycrypto_keys.generate_rsa_public_and_private(bits)
  else:
    message = 'Invalid crypto library: '+repr(_RSA_CRYPTO_LIBRARY)+'.'
    raise tuf.UnsupportedLibraryError(message) 
    
  # Generate the keyid of the RSA key.  'key_value' corresponds to the
  # 'keyval' entry of the 'RSAKEY_SCHEMA' dictionary.  The private key
  # information is not included in the generation of the 'keyid' identifier.
  key_value = {'public': public,
               'private': ''}
  keyid = _get_keyid(keytype, key_value)

  # Build the 'rsakey_dict' dictionary.  Update 'key_value' with the RSA
  # private key prior to adding 'key_value' to 'rsakey_dict'.
  key_value['private'] = private

  rsakey_dict['keytype'] = keytype
  rsakey_dict['keyid'] = keyid
  rsakey_dict['keyval'] = key_value

  return rsakey_dict





def generate_ed25519_key():
  """
  <Purpose> 
    Generate public and private ED25519 keys, both of length 32-bytes, although
    they are hexlified to 64 bytes.
    In addition, a keyid identifier generated for the returned ED25519 object.
    The object returned conforms to 'tuf.formats.ED25519KEY_SCHEMA' and has the
    form:
    {'keytype': 'ed25519',
     'keyid': 'f30a0870d026980100c0573bd557394f8c1bbd6...',
     'keyval': {'public': '9ccf3f02b17f82febf5dd3bab878b767d8408...',
                'private': 'ab310eae0e229a0eceee3947b6e0205dfab3...'}}
    
    The public and private keys are strings in PEM format and stored in the
    'keyval' field of the returned dictionary.

    >>> ed25519_key = generate_ed25519_key()
    >>> tuf.formats.ED25519KEY_SCHEMA.matches(ed25519_key)
    True
    >>> len(ed25519_key['keyval']['public'])
    64
    >>> len(ed25519_key['keyval']['private'])
    64

  <Arguments>
    None.
  
  <Exceptions>
    tuf.UnsupportedLibraryError, if an unsupported or unavailable library is
    detected.
  
  <Side Effects>
    The ED25519 keys are generated by calling either the optimized pure Python
    implementation of ed25519, or the ed25519 routines provided by 'pynacl'.

  <Returns>
    A dictionary containing the ED25519 keys and other identifying information.
    Conforms to 'tuf.formats.ED25519KEY_SCHEMA'. 
  """
  
  # Raise 'tuf.UnsupportedLibraryError' if the following libraries, specified
  # in 'tuf.conf', are unsupported or unavailable:
  # 'tuf.conf.RSA_CRYPTO_LIBRARY' and 'tuf.conf.ED25519_CRYPTO_LIBRARY'. 
  _check_crypto_libraries()

  # Begin building the ED25519 key dictionary. 
  ed25519_key = {}
  keytype = 'ed25519'
  public = None
  private = None

  # Generate the public and private ED25519 keys.  Use the 'pynacl' library
  # if available, otherwise fall back to optimized pure python implementation
  # provided by pyca and available in TUF.
  if 'pynacl' in _available_crypto_libraries:
    public, private = \
      tuf.ed25519_keys.generate_public_and_private(use_pynacl=True)
  else:
    public, private = \
      tuf.ed25519_keys.generate_public_and_private(use_pynacl=False)
    
  # Generate the keyid of the ED25519 key.  'key_value' corresponds to the
  # 'keyval' entry of the 'ED25519KEY_SCHEMA' dictionary.  The private key
  # information is not included in the generation of the 'keyid' identifier.
  key_value = {'public': binascii.hexlify(public),
               'private': ''}
  keyid = _get_keyid(keytype, key_value)

  # Build the 'ed25519_key' dictionary.  Update 'key_value' with the ED25519
  # private key prior to adding 'key_value' to 'ed25519_key'.
  key_value['private'] = binascii.hexlify(private)

  ed25519_key['keytype'] = keytype
  ed25519_key['keyid'] = keyid
  ed25519_key['keyval'] = key_value

  return ed25519_key





def format_keyval_to_metadata(keytype, key_value, private=False):
  """
  <Purpose>
    Return a dictionary conformant to 'tuf.formats.KEY_SCHEMA'.
    If 'private' is True, include the private key.  The dictionary
    returned has the form:
    {'keytype': keytype,
     'keyval': {'public': '...',
                'private': '...'}}
    
    or if 'private' is False:

    {'keytype': keytype,
     'keyval': {'public': '...',
                'private': ''}}
    
    TUF keys are stored in Metadata files (e.g., root.txt) in the format
    returned by this function.
    
    >>> ed25519_key = generate_ed25519_key()
    >>> key_val = ed25519_key['keyval']
    >>> keytype = ed25519_key['keytype']
    >>> ed25519_metadata = \
    format_keyval_to_metadata(keytype, key_val, private=True)
    >>> tuf.formats.KEY_SCHEMA.matches(ed25519_metadata)
    True
  
  <Arguments>
    key_type:
      The 'rsa' or 'ed25519' strings.      

    key_value:
      A dictionary containing a private and public keys.
      'key_value' is of the form:

      {'public': '...',
       'private': '...'}},
      
      conformant to 'tuf.formats.KEYVAL_SCHEMA'.

    private:
      Indicates if the private key should be included in the dictionary 
      returned.

  <Exceptions>
    tuf.FormatError, if 'key_value' does not conform to 
    'tuf.formats.KEYVAL_SCHEMA'.

  <Side Effects>
    None.

  <Returns>
    A 'tuf.formats.KEY_SCHEMA' dictionary.
  """

  # Does 'keytype' have the correct format?
  # This check will ensure 'keytype' has the appropriate number
  # of objects and object types, and that all dict keys are properly named.
  # Raise 'tuf.FormatError' if the check fails.
  tuf.formats.KEYTYPE_SCHEMA.check_match(keytype)
  
  # Does 'key_value' have the correct format?
  tuf.formats.KEYVAL_SCHEMA.check_match(key_value)

  if private is True and key_value['private']:
    return {'keytype': keytype, 'keyval': key_value}
  else:
    public_key_value = {'public': key_value['public'], 'private': ''}
    return {'keytype': keytype, 'keyval': public_key_value}





def format_metadata_to_key(key_metadata):
  """
  <Purpose>
    Construct a TUF key dictionary (e.g., tuf.formats.RSAKEY_SCHEMA)
    according to the keytype of 'key_metadata'.  The dict returned by this
    function has the exact format as the dict returned by one of the key
    generations functions, like generate_ed25519_key().  The dict returned
    has the form:
   
    {'keytype': keytype,
     'keyid': 'f30a0870d026980100c0573bd557394f8c1bbd6...',
     'keyval': {'public': '...',
                'private': '...'}}

    For example, RSA key dictionaries in RSAKEY_SCHEMA format should be used by
    modules storing a collection of keys, such as with keydb.py.  RSA keys as
    stored in metadata files use a different format, so this function should be
    called if an RSA key is extracted from one of these metadata files and need
    converting.  The key generation functions create an entirely new key and
    return it in the format appropriate for 'keydb.py'.
    
    >>> ed25519_key = generate_ed25519_key()
    >>> key_val = ed25519_key['keyval']
    >>> keytype = ed25519_key['keytype']
    >>> ed25519_metadata = \
    format_keyval_to_metadata(keytype, key_val, private=True)
    >>> ed25519_key_2 = format_metadata_to_key(ed25519_metadata)
    >>> tuf.formats.ED25519KEY_SCHEMA.matches(ed25519_key_2)
    True
    >>> ed25519_key == ed25519_key_2
    True

  <Arguments>
    key_metadata:
      The TUF key dictionary as stored in Metadata files, conforming to
      'tuf.formats.KEY_SCHEMA'.  It has the form:
      
      {'keytype': '...',
       'keyval': {'public': '...',
                  'private': '...'}}

  <Exceptions>
    tuf.FormatError, if 'key_metadata' does not conform to
    'tuf.formats.KEY_SCHEMA'.

  <Side Effects>
    None.

  <Returns>
    In the case of an RSA key, a dictionary conformant to
    'tuf.formats.RSAKEY_SCHEMA'.
  """

  # Does 'key_metadata' have the correct format?
  # This check will ensure 'key_metadata' has the appropriate number
  # of objects and object types, and that all dict keys are properly named.
  # Raise 'tuf.FormatError' if the check fails.
  tuf.formats.KEY_SCHEMA.check_match(key_metadata)

  # Construct the dictionary to be returned.
  key_dict = {}
  keytype = key_metadata['keytype']
  key_value = key_metadata['keyval']

  # Convert 'key_value' to 'tuf.formats.KEY_SCHEMA' and generate its hash
  # The hash is in hexdigest form. 
  keyid = _get_keyid(keytype, key_value)

  # All the required key values gathered.  Build 'key_dict'.
  key_dict['keytype'] = keytype
  key_dict['keyid'] = keyid
  key_dict['keyval'] = key_value

  return key_dict





def _get_keyid(keytype, key_value):
  """Return the keyid for 'key_value'."""

  # 'keyid' will be generated from an object conformant to KEY_SCHEMA,
  # which is the format Metadata files (e.g., root.txt) store keys.
  # 'format_keyval_to_metadata()' returns the object needed by _get_keyid().
  key_meta = format_keyval_to_metadata(keytype, key_value, private=False)

  # Convert the TUF key to JSON Canonical format, suitable for adding
  # to digest objects.
  key_update_data = tuf.formats.encode_canonical(key_meta)

  # Create a digest object and call update(), using the JSON 
  # canonical format of 'rskey_meta' as the update data.
  digest_object = tuf.hash.digest(_KEY_ID_HASH_ALGORITHM)
  digest_object.update(key_update_data)

  # 'keyid' becomes the hexadecimal representation of the hash.  
  keyid = digest_object.hexdigest()

  return keyid





def _check_crypto_libraries():
  """ Ensure all the crypto libraries specified in tuf.conf are available. """
 
  # The checks below all raise 'tuf.CryptoError' if the RSA and ED25519
  # crypto libraries specified in 'tuf.conf.py' are not supported or
  # unavailable.  The appropriate error message is added to the exception.
  # The funcions of this module that depend on user-installed crypto libraries 
  # should call this private function to ensure the called routine does not fail
  # with unpredictable exceptions in the event of a missing library.
  # The supported and available lists checked are populated when 'tuf.keys.py'
  # is imported.
  if _RSA_CRYPTO_LIBRARY not in _SUPPORTED_RSA_CRYPTO_LIBRARIES:
    message = 'The '+repr(_RSA_CRYPTO_LIBRARY)+' crypto library specified'+ \
      ' in "tuf.conf.RSA_CRYPTO_LIBRARY" is not supported.\n'+ \
      'Supported crypto libraries: '+repr(_SUPPORTED_RSA_CRYPTO_LIBRARIES)+'.'
    raise tuf.CryptoError(message)
  
  if _ED25519_CRYPTO_LIBRARY not in _SUPPORTED_ED25519_CRYPTO_LIBRARIES:
    message = 'The '+repr(_ED25519_CRYPTO_LIBRARY)+' crypto library specified'+\
      ' in "tuf.conf.ED25519_CRYPTO_LIBRARY" is not supported.\n'+ \
      'Supported crypto libraries: '+repr(_SUPPORTED_ED25519_CRYPTO_LIBRARIES)+'.'
    raise tuf.CryptoError(message)

  if _RSA_CRYPTO_LIBRARY not in _available_crypto_libraries:
    message = 'The '+repr(_RSA_CRYPTO_LIBRARY)+' crypto library specified'+ \
      ' in "tuf.conf.RSA_CRYPTO_LIBRARY" could not be imported.'
    raise tuf.CryptoError(message)
  
  if _ED25519_CRYPTO_LIBRARY not in _available_crypto_libraries:
    message = 'The '+repr(_ED25519_CRYPTO_LIBRARY)+' crypto library specified'+\
      ' in "tuf.conf.ED25519_CRYPTO_LIBRARY" could not be imported.'
    raise tuf.CryptoError(message)





def create_signature(key_dict, data):
  """
  <Purpose>
    Return a signature dictionary of the form:
    {'keyid': 'f30a0870d026980100c0573bd557394f8c1bbd6...',
     'method': '...',
     'sig': '...'}.

    The signing process will use the private key in 
    key_dict['keyval']['private'] and 'data' to generate the signature.

    The following signature methods are supported:

    'RSASSA-PSS' 
    RFC3447 - RSASSA-PSS 
    http://www.ietf.org/rfc/rfc3447.

    'ed25519'
    ed25519 - high-speed high security signatures 
    http://ed25519.cr.yp.to/

    Which signature to generate is determined by the key type of 'key_dict'
    and the available cryptography library specified in 'tuf.conf'.
    
    >>> ed25519_key = generate_ed25519_key()
    >>> data = 'The quick brown fox jumps over the lazy dog'
    >>> signature = create_signature(ed25519_key, data)
    >>> tuf.formats.SIGNATURE_SCHEMA.matches(signature)
    True
    >>> len(signature['sig'])
    128
    >>> rsa_key = generate_rsa_key(2048)
    >>> data = 'The quick brown fox jumps over the lazy dog'
    >>> signature = create_signature(rsa_key, data)
    >>> tuf.formats.SIGNATURE_SCHEMA.matches(signature)
    True

  <Arguments>
    key_dict:
      A dictionary containing the TUF keys.  An example RSA key dict has the
      form:
    
      {'keytype': 'rsa',
       'keyid': 'f30a0870d026980100c0573bd557394f8c1bbd6...',
       'keyval': {'public': '-----BEGIN RSA PUBLIC KEY----- ...',
                  'private': '-----BEGIN RSA PRIVATE KEY----- ...'}}

      The public and private keys are strings in PEM format.

    data:
      Data object used by create_signature() to generate the signature.

  <Exceptions>
    tuf.FormatError, if 'key_dict' is improperly formatted.
   
    tuf.UnsupportedLibraryError, if an unsupported or unavailable library is
    detected.

    TypeError, if 'key_dict' contains an invalid keytype.

  <Side Effects>
    The cryptography library specified in 'tuf.conf' called to perform the
    actual signing routine.

  <Returns>
    A signature dictionary conformat to 'tuf.format.SIGNATURE_SCHEMA'.
  """

  # Does 'key_dict' have the correct format?
  # This check will ensure 'key_dict' has the appropriate number of objects
  # and object types, and that all dict keys are properly named.
  # Raise 'tuf.FormatError' if the check fails.
  # The key type of 'key_dict' must be either 'rsa' or 'ed25519'.
  tuf.formats.ANYKEY_SCHEMA.check_match(key_dict)
  
  # Raise 'tuf.UnsupportedLibraryError' if the following libraries, specified
  # in 'tuf.conf', are unsupported or unavailable:
  # 'tuf.conf.RSA_CRYPTO_LIBRARY' and 'tuf.conf.ED25519_CRYPTO_LIBRARY'. 
  _check_crypto_libraries()

  # Signing the 'data' object requires a private key.
  # The 'RSASSA-PSS' (i.e., PyCrypto module) and 'ed25519' (i.e., PyNaCl and the
  # optimized pure Python implementation of ed25519) are the only signing
  # methods  currently supported.
  signature = {}
  keytype = key_dict['keytype']
  public = key_dict['keyval']['public']
  private = key_dict['keyval']['private']
  keyid = key_dict['keyid']
  method = None
  sig = None

  # Call the appropriate cryptography libraries for the supported key types,
  # otherwise raise an exception.
  if keytype == 'rsa':
    if _RSA_CRYPTO_LIBRARY == 'pycrypto':
      sig, method = tuf.pycrypto_keys.create_rsa_signature(private, data)
    else:
      message = 'Unsupported "tuf.conf.RSA_CRYPTO_LIBRARY": '+\
        repr(_RSA_CRYPTO_LIBRARY)+'.'
      raise tuf.UnsupportedLibraryError(message)
  
  elif keytype == 'ed25519':
    public = binascii.unhexlify(public)
    private = binascii.unhexlify(private)
    if _ED25519_CRYPTO_LIBRARY == 'pynacl' \
                  and 'pynacl' in _available_crypto_libraries:
      sig, method = tuf.ed25519_keys.create_signature(public, private,
                                                      data, use_pynacl=True)
    
    # Fall back to using the optimized pure python implementation of ed25519. 
    else:
      sig, method = tuf.ed25519_keys.create_signature(public, private,
                                                      data, use_pynacl=False)
  else:
    raise TypeError('Invalid key type.')
    
  # Build the signature dictionary to be returned.
  # The hexadecimal representation of 'sig' is stored in the signature.
  signature['keyid'] = keyid
  signature['method'] = method
  signature['sig'] = binascii.hexlify(sig)

  return signature





def verify_signature(key_dict, signature, data):
  """
  <Purpose>
    Determine whether the private key belonging to 'key_dict' produced
    'signature'.  verify_signature() will use the public key found in
    'key_dict', the 'method' and 'sig' objects contained in 'signature',
    and 'data' to complete the verification.

    >>> ed25519_key = generate_ed25519_key()
    >>> data = 'The quick brown fox jumps over the lazy dog'
    >>> signature = create_signature(ed25519_key, data)
    >>> verify_signature(ed25519_key, signature, data)
    True
    >>> verify_signature(ed25519_key, signature, 'bad_data')
    False
    >>> rsa_key = generate_rsa_key()
    >>> signature = create_signature(rsa_key, data)
    >>> verify_signature(rsa_key, signature, data)
    True
    >>> verify_signature(rsa_key, signature, 'bad_data')
    False

  <Arguments>
    key_dict:
      A dictionary containing the TUF keys and other identifying information.
      If 'key_dict' is an RSA key, it has the form:
     
      {'keytype': 'rsa',
       'keyid': 'f30a0870d026980100c0573bd557394f8c1bbd6...',
       'keyval': {'public': '-----BEGIN RSA PUBLIC KEY----- ...',
                  'private': '-----BEGIN RSA PRIVATE KEY----- ...'}}

      The public and private keys are strings in PEM format.
      
    signature:
      The signature dictionary produced by one of the key generation functions.
      'signature' has the form:
      
      {'keyid': 'f30a0870d026980100c0573bd557394f8c1bbd6...',
       'method': 'method',
       'sig': sig}.
      
      Conformant to 'tuf.formats.SIGNATURE_SCHEMA'.
      
    data:
      Data object used by tuf.rsa_key.create_signature() to generate
      'signature'.  'data' is needed here to verify the signature.

  <Exceptions>
    tuf.FormatError, raised if either 'key_dict' or 'signature' are improperly
    formatted.
    
    tuf.UnsupportedLibraryError, if an unsupported or unavailable library is
    detected.
    
    tuf.UnknownMethodError.  Raised if the signing method used by
    'signature' is not one supported.

  <Side Effects>
    The cryptography library specified in 'tuf.conf' called to do the actual
    verification.

  <Returns>
    Boolean.  True if the signature is valid, False otherwise.
  """

  # Does 'key_dict' have the correct format?
  # This check will ensure 'key_dict' has the appropriate number
  # of objects and object types, and that all dict keys are properly named.
  # Raise 'tuf.FormatError' if the check fails.
  tuf.formats.ANYKEY_SCHEMA.check_match(key_dict)

  # Does 'signature' have the correct format?
  tuf.formats.SIGNATURE_SCHEMA.check_match(signature)
  
  # Using the public key belonging to 'key_dict'
  # (i.e., rsakey_dict['keyval']['public']), verify whether 'signature'
  # was produced by key_dict's corresponding private key
  # key_dict['keyval']['private'].
  method = signature['method']
  sig = signature['sig']
  sig = binascii.unhexlify(sig)
  public = key_dict['keyval']['public']
  keytype = key_dict['keytype']
  valid_signature = False
  
  # Call the appropriate cryptography libraries for the supported key types,
  # otherwise raise an exception.
  if keytype == 'rsa':
    if _RSA_CRYPTO_LIBRARY == 'pycrypto':
      valid_signature = tuf.pycrypto_keys.verify_rsa_signature(sig, method,
                                                               public, data) 
    else:
      message = 'Unsupported "tuf.conf.RSA_CRYPTO_LIBRARY": '+\
        repr(_RSA_CRYPTO_LIBRARY)+'.'
      raise tuf.UnsupportedLibraryError(message) 
  
  elif keytype == 'ed25519':
    public = binascii.unhexlify(public)
    if _RSA_CRYPTO_LIBRARY == 'pynacl' and \
                              'pynacl' in _available_crypto_libraries:
      valid_signature = tuf.ed25519_keys.verify_signature(public,
                                                          method, sig, data,
                                                          use_pynacl=True)
    # Fall back to the optimized pure python implementation of ed25519. 
    else:
      valid_signature = tuf.ed25519_keys.verify_signature(public,
                                                          method, sig, data,
                                                          use_pynacl=False)
  else:
    raise TypeError('Unsupported key type.')

  return valid_signature 





def import_rsakey_from_encrypted_pem(encrypted_pem, password):
  """
  <Purpose> 
    Generate public and private RSA keys, with modulus length 'bits'.  In
    addition, a keyid identifier for the RSA key is generated.  The object
    returned conforms to 'tuf.formats.RSAKEY_SCHEMA' and has the
    form:
    {'keytype': 'rsa',
     'keyid': keyid,
     'keyval': {'public': '-----BEGIN RSA PUBLIC KEY----- ...',
                'private': '-----BEGIN RSA PRIVATE KEY----- ...'}}
    
    The public and private keys are strings in PEM format.

    Although the PyCrypto crytography library called sets a 1024-bit minimum
    key size, generate() enforces a minimum key size of 2048 bits.  If 'bits' is
    unspecified, a 3072-bit RSA key is generated, which is the key size
    recommended by TUF. 
    
    >>> rsa_key = generate_rsa_key()
    >>> private = rsa_key['keyval']['private']
    >>> passphrase = 'secret'
    >>> encrypted_pem = create_rsa_encrypted_pem(private, passphrase) 
    >>> rsa_key2 = import_rsakey_from_encrypted_pem(encrypted_pem, passphrase)
    >>> rsa_key == rsa_key2
    True
  
  <Arguments>
    encrypted_pem:
      The key size, or key length, of the RSA key.  'bits' must be 2048, or
      greater, and a multiple of 256.

    password:

  <Exceptions>
    tuf.FormatError, if 'bits' is improperly or invalid (i.e., not an integer
    and not at least 2048).
   
    tuf.UnsupportedLibraryError, if any of the cryptography libraries specified
    in 'tuf.conf.py' are unsupported or unavailable.

    ValueError, if an exception occurs after calling the RSA key generation
    routine.  'bits' must be a multiple of 256.  The 'ValueError' exception is
    raised by the key generation function of the cryptography library called.

  <Side Effects>
    The RSA keys are generated by calling PyCrypto's
    Crypto.PublicKey.RSA.generate().

  <Returns>
    A dictionary containing the RSA keys and other identifying information.
    Conforms to 'tuf.formats.RSAKEY_SCHEMA'. 
  """

  # Does 'encrypted_pem' have the correct format?
  # This check will ensure 'encrypted_pem' conforms to
  # 'tuf.formats.PEMRSA_SCHEMA'.
  tuf.formats.PEMRSA_SCHEMA.check_match(encrypted_pem)

  # Does 'password' have the correct format?
  tuf.formats.PASSWORD_SCHEMA.check_match(password)

  # Raise 'tuf.UnsupportedLibraryError' if the following libraries, specified in
  # 'tuf.conf', are unsupported or unavailable:
  # 'tuf.conf.RSA_CRYPTO_LIBRARY' and 'tuf.conf.ED25519_CRYPTO_LIBRARY'. 
  _check_crypto_libraries()

  # Begin building the RSA key dictionary. 
  rsakey_dict = {}
  keytype = 'rsa'
  public = None
  private = None

  # Generate the public and private RSA keys.  The PyCrypto module performs
  # the actual key generation.  Raise 'ValueError' if 'bits' is less than 1024 
  # or not a multiple of 256, although a 2048-bit minimum is enforced by
  # tuf.formats.RSAKEYBITS_SCHEMA.check_match().
  if _RSA_CRYPTO_LIBRARY == 'pycrypto':
    public, private = \
      tuf.pycrypto_keys.create_rsa_public_and_private_from_encrypted_pem(encrypted_pem,
                                                                         password)
  else:
    message = 'Invalid crypto library: '+repr(_RSA_CRYPTO_LIBRARY)+'.'
    raise tuf.UnsupportedLibraryError(message) 
    
  # Generate the keyid of the RSA key.  'key_value' corresponds to the
  # 'keyval' entry of the 'RSAKEY_SCHEMA' dictionary.  The private key
  # information is not included in the generation of the 'keyid' identifier.
  key_value = {'public': public,
               'private': ''}
  keyid = _get_keyid(keytype, key_value)

  # Build the 'rsakey_dict' dictionary.  Update 'key_value' with the RSA
  # private key prior to adding 'key_value' to 'rsakey_dict'.
  key_value['private'] = private

  rsakey_dict['keytype'] = keytype
  rsakey_dict['keyid'] = keyid
  rsakey_dict['keyval'] = key_value

  return rsakey_dict





def format_rsakey_from_pem(pem):
  """
  <Purpose> 
    Generate public and private RSA keys, with modulus length 'bits'.  In
    addition, a keyid identifier for the RSA key is generated.  The object
    returned conforms to 'tuf.formats.RSAKEY_SCHEMA' and has the
    form:
    {'keytype': 'rsa',
     'keyid': keyid,
     'keyval': {'public': '-----BEGIN RSA PUBLIC KEY----- ...',
                'private': ''}}
    
    The public and private keys are strings in PEM format.

    Although the PyCrypto crytography library called sets a 1024-bit minimum
    key size, generate() enforces a minimum key size of 2048 bits.  If 'bits' is
    unspecified, a 3072-bit RSA key is generated, which is the key size
    recommended by TUF. 
    
    >>>
    >>>
    >>>

  <Arguments>
    pem:
      The key size, or key length, of the RSA key.  'bits' must be 2048, or
      greater, and a multiple of 256.

  <Exceptions>
    tuf.FormatError, if 'bits' is improperly or invalid (i.e., not an integer
    and not at least 2048).
   
    tuf.UnsupportedLibraryError, if any of the cryptography libraries specified
    in 'tuf.conf.py' are unsupported or unavailable.

    ValueError, if an exception occurs after calling the RSA key generation
    routine.  'bits' must be a multiple of 256.  The 'ValueError' exception is
    raised by the key generation function of the cryptography library called.

  <Side Effects>
    The RSA keys are generated by calling PyCrypto's
    Crypto.PublicKey.RSA.generate().

  <Returns>
    A dictionary containing the RSA keys and other identifying information.
    Conforms to 'tuf.formats.RSAKEY_SCHEMA'. 
  """

  # Does 'pem' have the correct format?
  # This check will ensure 'pem' conforms to
  # 'tuf.formats.PEMRSA_SCHEMA'.
  tuf.formats.PEMRSA_SCHEMA.check_match(pem)

  # Begin building the RSA key dictionary. 
  rsakey_dict = {}
  keytype = 'rsa'
  public = pem 

  # Generate the keyid of the RSA key.  'key_value' corresponds to the
  # 'keyval' entry of the 'RSAKEY_SCHEMA' dictionary.  The private key
  # information is not included in the generation of the 'keyid' identifier.
  key_value = {'public': public,
               'private': ''}
  keyid = _get_keyid(keytype, key_value)

  rsakey_dict['keytype'] = keytype
  rsakey_dict['keyid'] = keyid
  rsakey_dict['keyval'] = key_value

  return rsakey_dict





def create_rsa_encrypted_pem(private_key, passphrase):
  """
  <Purpose>
    Return a string in PEM format, where the private part of the RSA key is
    encrypted.  The private part of the RSA key is encrypted by the Triple
    Data Encryption Algorithm (3DES) and Cipher-block chaining (CBC) for the 
    mode of operation.  Password-Based Key Derivation Function 1 (PBKF1) + MD5
    is used to strengthen 'passphrase'.

    https://en.wikipedia.org/wiki/Triple_DES
    https://en.wikipedia.org/wiki/PBKDF2

    >>> rsa_key = generate_rsa_key()
    >>> private = rsa_key['keyval']['private']
    >>> passphrase = 'secret'
    >>> encrypted_pem = create_rsa_encrypted_pem(private, passphrase)
    >>> tuf.formats.PEMRSA_SCHEMA.matches(encrypted_pem)
    True

  <Arguments>
    private_key:
      The private key string in PEM format.

    passphrase:
      The passphrase, or password, to encrypt the private part of the RSA
      key.  'passphrase' is not used directly as the encryption key, a stronger
      encryption key is derived from it. 

  <Exceptions>
    tuf.FormatError, if the arguments are improperly formatted.

    tuf.CryptoError, if an RSA key in encrypted PEM format cannot be created.

    TypeError, 'private_key' is unset. 

  <Side Effects>
    PyCrypto's Crypto.PublicKey.RSA.exportKey() called to perform the actual
    generation of the PEM-formatted output.

  <Returns>
    A string in PEM format, where the private RSA key is encrypted.
    Conforms to 'tuf.formats.PEMRSA_SCHEMA'.
  """
  
  # Does 'private_key' have the correct format?
  # This check will ensure 'private_key' has the appropriate number
  # of objects and object types, and that all dict keys are properly named.
  # Raise 'tuf.FormatError' if the check fails.
  tuf.formats.PEMRSA_SCHEMA.check_match(private_key)
  
  # Does 'passphrase' have the correct format?
  tuf.formats.PASSWORD_SCHEMA.check_match(passphrase)

  encrypted_pem = None
  
  # Generate the public and private RSA keys.  The PyCrypto module performs
  # the actual key generation.  Raise 'ValueError' if 'bits' is less than 1024 
  # or not a multiple of 256, although a 2048-bit minimum is enforced by
  # tuf.formats.RSAKEYBITS_SCHEMA.check_match().
  if _RSA_CRYPTO_LIBRARY == 'pycrypto':
    encrypted_pem = \
      tuf.pycrypto_keys.create_rsa_encrypted_pem(private_key, passphrase)
  else:
    message = 'Invalid crypto library: '+repr(_RSA_CRYPTO_LIBRARY)+'.'
    raise tuf.UnsupportedLibraryError(message) 

  return encrypted_pem




if __name__ == '__main__':
  # The interactive sessions of the documentation strings can
  # be tested by running 'keys.py' as a standalone module.
  # python keys.py
  import doctest
  doctest.testmod()