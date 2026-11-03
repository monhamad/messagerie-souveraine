{
  "realm": "souverain",
  "enabled": true,
  "displayName": "Messagerie souveraine",
  "sslRequired": "external",
  "registrationAllowed": false,
  "resetPasswordAllowed": false,
  "rememberMe": false,
  "loginWithEmailAllowed": false,
  "duplicateEmailsAllowed": true,
  "verifyEmail": false,
  "editUsernameAllowed": false,
  "bruteForceProtected": true,
  "failureFactor": 5,
  "waitIncrementSeconds": 60,
  "maxFailureWaitSeconds": 900,
  "permanentLockout": false,
  "passwordPolicy": "length(12) and digits(1) and upperCase(1) and lowerCase(1) and specialChars(1)",
  "otpPolicyType": "totp",
  "otpPolicyAlgorithm": "HmacSHA1",
  "otpPolicyDigits": 6,
  "otpPolicyPeriod": 30,
  "ssoSessionIdleTimeout": 1800,
  "ssoSessionMaxLifespan": 36000,
  "accessTokenLifespan": 300,
  "requiredActions": [
    {
      "alias": "CONFIGURE_TOTP",
      "name": "Configure OTP",
      "providerId": "CONFIGURE_TOTP",
      "enabled": true,
      "defaultAction": true,
      "priority": 10
    }
  ],
  "clients": [
    {
      "clientId": "synapse",
      "name": "Messagerie souveraine (Synapse)",
      "enabled": true,
      "protocol": "openid-connect",
      "publicClient": false,
      "secret": "__OIDC_SECRET__",
      "standardFlowEnabled": true,
      "implicitFlowEnabled": false,
      "directAccessGrantsEnabled": false,
      "serviceAccountsEnabled": false,
      "redirectUris": ["__PUBLIC_URL__/_synapse/client/oidc/callback"],
      "webOrigins": []
    }
  ],
  "users": [
__USERS__
  ]
}
