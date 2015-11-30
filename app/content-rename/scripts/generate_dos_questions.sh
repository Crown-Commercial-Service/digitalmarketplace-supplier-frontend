#!/bin/sh
#
# Generate DOS questions for specialist roles and outcome capabilities.
#
# Usage:
#   FRAMEWORKS_PATH=frameworks/digital-outcomes-and-specialists/questions/services/ ./scripts/generate_dos_questions.sh

make_questions() {
    local specialist="$(tr '[:lower:]' '[:upper:]' <<< ${1:0:1})${1:1}"
    sed -e "s/NAME/$specialist/" -e "s/TYPE/$1/" -e "s/QUESTION/$2/" > ${FRAMEWORKS_PATH}${2}.yml <<END
question: NAME
name: NAME
optional: true
depends:
  - "on": lot
    being:
      - digital-specialists
type: multiquestion
any_of: specialist
questions:
  - QUESTIONLocations
  - QUESTIONDayRate

empty_message: You haven't added a TYPE
END

    sed -e "s/TYPE/$1/" -e "s/QUESTION/$2/" > ${FRAMEWORKS_PATH}${2}DayRate.yml <<END
question: How much do you charge per day for a TYPE?
depends:
  - "on": lot
    being:
      - digital-specialists
type: pricing
fields:
  minimum_price: QUESTIONPriceMin
  maximum_price: QUESTIONPriceMax
field_defaults:
  price_unit: Person
  price_interval: Day

validations:
  - name: answer_required
    field: QUESTIONPriceMin
    message: 'You need to answer this question.'
  - name: answer_required
    field: QUESTIONPriceMax
    message: 'You need to answer this question.'
END

    sed -e "s/TYPE/$1/" -e "s/QUESTION/$2/" > ${FRAMEWORKS_PATH}${2}Locations.yml <<END
question: Where will your TYPE work?
depends:
  - "on": lot
    being:
      - digital-specialists
type: checkboxes
options:
  - label: "Off-site"
  - label: "Scotland"
  - label: "North East England"
  - label: "North West England"
  - label: "Yorkshire and the Humber"
  - label: "East Midlands"
  - label: "The Midlands"
  - label: "East England"
  - label: "Wales"
  - label: "London"
  - label: "South East England"
  - label: "West England"
  - label: "Northern Ireland"

validations:
  - name: answer_required
    message: 'You need to answer this question.'
END
}

make_questions "agile coach" "agileCoach"
make_questions "business analyst" "businessAnalyst"
make_questions "communications manager" "communicationsManager"
make_questions "content designer" "contentDesigner"
make_questions "cyber security consultant" "securityConsultant"
make_questions "delivery manager" "deliveryManager"
make_questions "designer" "designer"
make_questions "developer" "developer"
make_questions "performance analyst" "performanceAnalyst"
make_questions "portfolio manager" "portfolioManager"
make_questions "product manager" "productManager"
make_questions "programme manager" "programmeManager"
make_questions "quality assurance analyst" "qualityAssurance"
make_questions "service manager" "serviceManager"
make_questions "technical architect" "technicalArchitect"
make_questions "user researcher" "userResearcher"
make_questions "web operations engineer" "webOperations"

sed -i '' 's/a agile coach/an agile coach/g' ${FRAMEWORKS_PATH}/*.yml

make_outcomes_multiquestion() {
    local capability="$(tr '[:lower:]' '[:upper:]' <<< ${1:0:1})${1:1}"
    sed -e "s/NAME/$capability/" -e "s/TYPE/$1/" -e "s/QUESTION/$2/" > ${FRAMEWORKS_PATH}${2}.yml <<END
question: NAME
name: NAME
optional: true
depends:
  - "on": lot
    being:
      - digital-outcomes
type: multiquestion
any_of: capability
questions:
  - QUESTIONTypes

empty_message: You haven't added any TYPE capabilities
END
}

make_outcomes_multiquestion "performance analysis and data" performanceAnalysis
make_outcomes_multiquestion "security" security
make_outcomes_multiquestion "service delivery" delivery
make_outcomes_multiquestion "software development" softwareDevelopment
make_outcomes_multiquestion "support and operations" supportAndOperations
make_outcomes_multiquestion "testing and auditing" testingAndAuditing
make_outcomes_multiquestion "user experience and design" userExperienceAndDesign
make_outcomes_multiquestion "user research" userResearch
