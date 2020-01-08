/* eslint new-cap: ["error", { "newIsCap": false }] */

describe('GOVUK.PII', () => {
  let pii

  beforeAll(() => {
    require('../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/analytics/_govukAnalytics.js')
    require('../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/analytics/_pii.js')
  })

  beforeEach(() => {
    pii = new GOVUK.pii()
  })

  afterEach(() => {
    resetHead()
  })

  describe('by default', () => {
    it('strips email addresses, but not postcodes and dates from strings', () => {
      const results = pii.stripPII('this is an@email.com address, this is a sw1a 1aa postcode, this is a 2019-01-21 date')
      expect(results).toEqual('this is [email] address, this is a sw1a 1aa postcode, this is a 2019-01-21 date')
    })

    it('strips email addresses but not dates and postcodes from objects', () => {
      const obj = {
        email: 'this is an@email.com address',
        postcode: 'this is a sw1a 1aa postcode',
        date: 'this is a 2019-01-21 date'
      }

      const strippedObj = {
        email: 'this is [email] address',
        postcode: 'this is a sw1a 1aa postcode',
        date: 'this is a 2019-01-21 date'
      }

      const results = pii.stripPII(obj)
      expect(results).toEqual(strippedObj)
    })

    it('strips email addresses but not dates and postcodes from arrays', () => {
      const arr = [
        'this is an@email.com address',
        'this is a sw1a 1aa postcode',
        'this is a 2019-01-21 date'
      ]

      const strippedArr = [
        'this is [email] address',
        'this is a sw1a 1aa postcode',
        'this is a 2019-01-21 date'
      ]

      const results = pii.stripPII(arr)
      expect(results).toEqual(strippedArr)
    })
  })

  describe('when configured to remove all PII', () => {
    beforeEach(() => {
      pageWantsDatesStripped()
      pageWantsPostcodesStripped()
      pii = new GOVUK.pii()
    })

    it('strips email addresses, postcodes and dates from strings', () => {
      const results = pii.stripPII('this is an@email.com address, this is a sw1a 1aa postcode, this is a 2019-01-21 date')
      expect(results).toEqual('this is [email] address, this is a [postcode] postcode, this is a [date] date')
    })

    it('strips all PII from objects', () => {
      const obj = {
        email: 'this is an@email.com address',
        postcode: 'this is a sw1a 1aa postcode',
        date: 'this is a 2019-01-21 date'
      }

      const strippedObj = {
        email: 'this is [email] address',
        postcode: 'this is a [postcode] postcode',
        date: 'this is a [date] date'
      }

      const results = pii.stripPII(obj)
      expect(results).toEqual(strippedObj)
    })

    it('strips all PII from arrays', () => {
      const arr = [
        'this is an@email.com address',
        'this is a sw1a 1aa postcode',
        'this is a 2019-01-21 date'
      ]

      const strippedArr = [
        'this is [email] address',
        'this is a [postcode] postcode',
        'this is a [date] date'
      ]

      const results = pii.stripPII(arr)
      expect(results).toEqual(strippedArr)
    })
  })

  describe('when there is a a govuk:static-analytics:strip-postcodes meta tag present', () => {
    beforeEach(() => {
      pageWantsPostcodesStripped()
      pii = new GOVUK.pii()
    })

    it('observes the meta tag and strips out postcodes', () => {
      expect(pii.stripPostcodePII).toBeTruthy()
      const result = pii.stripPII('this is an@email.com address, this is a sw1a 1aa postcode, this is a 2019-01-21 date')
      expect(result).toEqual('this is [email] address, this is a [postcode] postcode, this is a 2019-01-21 date')
    })
  })

  describe('when there is a a govuk:static-analytics:strip-dates meta tag present', () => {
    beforeEach(() => {
      pageWantsDatesStripped()
      pii = new GOVUK.pii()
    })

    it('observes the meta tag and strips out postcodes', () => {
      expect(pii.stripDatePII).toBeTruthy()
      const results = pii.stripPII('this is an@email.com address, this is a sw1a 1aa postcode, this is a 2019-01-21 date')
      expect(results).toEqual('this is [email] address, this is a sw1a 1aa postcode, this is a [date] date')
    })
  })

  const resetHead = () => {
    // Rather long winded way to remove the meta tags in the head
    // this is to resolve "'remove()' is not a function" error when the
    // element does not exist
    const stripPostcodesMetaTAG = (document.querySelector('meta[name="govuk:static-analytics:strip-postcodes"]') || { remove: () => 0 })
    const stripDatesMetaTAG = (document.querySelector('meta[name="govuk:static-analytics:strip-dates"]') || { remove: () => 0 })

    // Removes the tags if not and should not raise an error if they do not exist
    stripPostcodesMetaTAG.remove()
    stripDatesMetaTAG.remove()
  }

  const pageWantsDatesStripped = () => {
    const metaTAG = document.createElement('meta')
    metaTAG.value = 'does not matter'
    metaTAG.name = 'govuk:static-analytics:strip-dates'

    document.querySelector('head').appendChild(metaTAG)
  }

  const pageWantsPostcodesStripped = () => {
    const metaTAG = document.createElement('meta')
    metaTAG.value = 'does not matter'
    metaTAG.name = 'govuk:static-analytics:strip-postcodes'

    document.querySelector('head').appendChild(metaTAG)
  }
})
