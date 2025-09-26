Feature: feedback endpoint API tests


  Background:
    Given The service is started locally
      And REST API service hostname is localhost
      And REST API service port is 8080
      And REST API service prefix is /v1

  Scenario: Check if enabling the feedback is working
    Given The system is in default state
     When I allow the feedback
     Then The status code of the response is 200
     And The body of the response has the following schema
          """
            {
                "status": 
                    {
                        "updated_status": true,
                    }
            }
          """
    
  Scenario: Check if disabling the feedback is working
    Given The system is in default state
     When I disable the feedback
     Then The status code of the response is 200
     And The body of the response has the following schema
          """
            {
                "status": 
                    {
                        "updated_status": false,
                    }
            }
          """

  Scenario: Check if toggling the feedback with no status attribute fails
    Given The system is in default state
     When I toggle the feedback with  
     """
        {
            "no_status": true,
        }
     """
     Then The status code of the response is 422
     And The body of the response has the following schema
          """
            {
            "detail": [
                {
                "type": "json_invalid",
                "loc": [
                    "body",
                ],
                "msg": "JSON decode error",
                }
            ]
            }
          """

  Scenario: Check if toggling the feedback with incorrect status value fails
    Given The system is in default state
     When I toggle the feedback with  
     """
        {
            "status": "no_bool",
        }
     """
     Then The status code of the response is 422
     And The body of the response has the following schema
          """
            {
            "detail": [
                {
                "type": "json_invalid",
                "loc": [
                    "body",
                ],
                "msg": "JSON decode error",
                }
            ]
            }
          """
          

  Scenario: Check if GET feedback/status endpoint is working when feedback is enabled
    Given The system is in default state
    And The feedback is enabled
     When I access REST API endpoint "feedback/status" using HTTP GET method
     Then The status code of the response is 200
     And The body of the response is the following
          """
          {"functionality": "feedback", "status": { "enabled": true}}
          """

  Scenario: Check if GET feedback/status endpoint is working when feedback is disabled
    Given The system is in default state
    And The feedback is disabled
     When I access REST API endpoint "feedback/status" using HTTP GET method
     Then The status code of the response is 200
     And The body of the response is the following
          """
          {"functionality": "feedback", "status": { "enabled": false}}
          """

  Scenario: Check if feedback endpoint is not working when not authorized
    Given The system is in default state
    And I remove the auth header
     When I access endpoint "feedback" using HTTP POST with conversation ID "conversationID"
          """
            {
                "llm_response": "bar",
                "sentiment": -1,
                "user_feedback": "Not satisfied with the response quality",
                "user_question": "random question"
            }
          """
     Then The status code of the response is 400
     And The body of the response is the following
          """
            {
                "detail": "Unauthorized: No auth header found"
            }
          """

  Scenario: Check if feedback endpoint is not working when feedback is disabled
    Given The system is in default state
     When I disable the feedback
     When I access endpoint "feedback" using HTTP POST with conversation ID "conversationID"
          """
            {
                "llm_response": "bar",
                "sentiment": -1,
                "user_feedback": "Not satisfied with the response quality",
                "user_question": "random question"
            }
          """
     Then The status code of the response is 403
     And The body of the response is the following
          """
            {
                "detail": "Forbidden: Feedback is disabled"
            }   
          """

  Scenario: Check if feedback endpoint fails with incorrect body format when conversationID is not present
    Given The system is in default state
     When I access endpoint "feedback" using HTTP POST method
          """
          {
              "llm_response": "bar",
              "sentiment": -1,
              "user_feedback": "Not satisfied with the response quality",
              "user_question": "random question"
          }
          """
     Then The status code of the response is 422
     And The body of the response has the following schema
          """
          { "type": "missing", "loc": [ "body", "conversation_id" ], "msg": "Field required", }
          """

  Scenario: Check if feedback endpoint is working when feedback is enabled
    Given The system is in default state
    And The feedback is enabled
     When I access endpoint "feedback" using HTTP POST with conversation ID "conversationID"
          """
            {
                "llm_response": "bar",
                "sentiment": -1,
                "user_feedback": "Not satisfied with the response quality",
                "user_question": "random question"
            }
          """
     Then The status code of the response is 200
     And The body of the response is the following
          """
            {
                "response": "feedback received"
            }
          """