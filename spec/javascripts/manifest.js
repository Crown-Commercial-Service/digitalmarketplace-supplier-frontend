// files are loaded from the /spec/javascripts/support folder so paths are relative to that
var manifest = {
  support : [
    '../../../node_modules/jquery/dist/jquery.js',
    '../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/analytics/_pii.js',
    '../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/analytics/_googleAnalyticsUniversalTracker.js',
    '../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/analytics/_govukAnalytics.js',
    '../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/analytics/_register.js',
    '../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/analytics/_pageViews.js',
    '../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/analytics/_virtualPageViews.js',
    '../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/analytics/_trackExternalLinks.js',
    '../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/analytics/_init.js',
    '../../../app/assets/javascripts/analytics/_events.js',
  ],
  test : [
    '../unit/AnalyticsSpec.js',
    '../unit/piiSpec.js'
  ]
};

if (typeof exports !== 'undefined') {
  exports.manifest = manifest;
}
