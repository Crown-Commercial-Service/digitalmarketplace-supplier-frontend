var gulp = require('gulp');
var uglify = require('gulp-uglifyjs');
var deleteFiles = require('del');
var sass = require('gulp-sass');
var include = require('gulp-include');

var environment;
var repoRoot = __dirname + '/';
var govukToolkitSCSS = repoRoot + 'node_modules/govuk_frontend_toolkit/stylesheets';
var dmToolkitSCSS = repoRoot + 'bower_components/digitalmarketplace-frontend-toolkit/toolkit/scss';
var assetsFolder = repoRoot + 'app/assets';
var staticFolder = repoRoot + 'app/static';
var govukTemplateAssetsFolder = repoRoot + 'bower_components/govuk_template/assets';
var dmToolkitAssetsFolder = repoRoot + 'bower_components/digitalmarketplace-frontend-toolkit/toolkit/';

// JavaScript paths
var jsVendorFiles = [
  assetsFolder + '/javascripts/vendor/jquery-1.11.0.js',
  assetsFolder + '/javascripts/vendor/hogan-3.0.2.min.js'
];
var jsSourceFiles = [
  assetsFolder + '/javascripts/application.js'
];
var jsDistributionFolder = staticFolder + '/javascripts';
var jsDistributionFile = 'application.js';

// CSS paths
var cssSourceGlob = assetsFolder + '/scss/**/*.scss';
var cssDistributionFolder = staticFolder + '/stylesheets';

// Configuration
var sassOptions = {
  development: {
    outputStyle: 'expanded',
    lineNumbers: true,
    includePaths: [govukToolkitSCSS, dmToolkitSCSS],
    sourceComments: true
  },
  production: {
    outputStyle: 'compressed',
    lineNumbers: true,
    includePaths: [govukToolkitSCSS, dmToolkitSCSS]
  },
};

var uglifyOptions = {
  development: {
    mangle: false,
    output: {
      beautify: true,
      semicolons: true,
      comments: true,
      indent_level: 2
    }
  },
  production: {
    mangle: true
  }
};

gulp.task('clean', function () {
  var logOutputFor = function (fileType) {
    return function (err, paths) {
      console.log('Deleted the following ' + fileType + ' files:\n', paths.join('\n'));
    };
  };

  deleteFiles(jsDistributionFolder + '/*.js', logOutputFor('JavaScript'));
  deleteFiles(cssDistributionFolder + '/*.css', logOutputFor('CSS'));
});

gulp.task('sass', function () {
  var stream = gulp.src(cssSourceGlob)
    .pipe(sass(sassOptions[environment]))
    .on('error', function (err) {
      console.log(err.message);
    })
    .pipe(gulp.dest(cssDistributionFolder));

  stream.on('end', function () {
    console.log('Compressed CSS saved as .css files in ' + cssDistributionFolder);
  });

  return stream;
});

gulp.task('js', function () {
  // produce full array of JS files from vendor + local scripts
  jsFiles = jsVendorFiles.concat(jsSourceFiles);
  var stream = gulp.src(jsFiles)
    .pipe(include())
    .pipe(uglify(
      jsDistributionFile,
      uglifyOptions[environment]
    ))
    .pipe(gulp.dest(jsDistributionFolder));

  stream.on('end', function () {
    console.log('Compressed JavaScript saved as ' + jsDistributionFolder + '/' + jsDistributionFile)
  });

  return stream;
});

gulp.task('copy_template_assets:stylesheets', function () {
  return gulp.src(govukTemplateAssetsFolder + '/stylesheets/**/*', { base : govukTemplateAssetsFolder + '/stylesheets' })
    .pipe(gulp.dest(staticFolder + '/stylesheets'))
});

gulp.task('copy_template_assets:images', function () {
  return gulp.src(govukTemplateAssetsFolder + '/images/**/*', { base : govukTemplateAssetsFolder + '/images' })
    .pipe(gulp.dest(staticFolder + '/images'))
});

gulp.task('copy_template_assets:javascripts', function () {
  return gulp.src(govukTemplateAssetsFolder + '/javascripts/**/*', { base : govukTemplateAssetsFolder + '/javascripts' })
    .pipe(gulp.dest(staticFolder + '/javascripts'))
});

gulp.task('copy_template_assets', function () {
   gulp.start('copy_template_assets:stylesheets');
   gulp.start('copy_template_assets:images');
   gulp.start('copy_template_assets:javascripts');
});

gulp.task('watch', ['build:development'], function () {
  var jsWatcher = gulp.watch([ assetsFolder + '/**/*.js' ], ['js']);
  var cssWatcher = gulp.watch([ assetsFolder + '/**/*.scss' ], ['sass']);
  var notice = function (event) {
    console.log('File ' + event.path + ' was ' + event.type + ' running tasks...');
  };

  cssWatcher.on('change', notice);
  jsWatcher.on('change', notice);
});

gulp.task('copy_toolkit_assets:images', function () {
  return gulp.src(dmToolkitAssetsFolder + '/images/**/*', { base : dmToolkitAssetsFolder + '/images' })
    .pipe(gulp.dest(staticFolder + '/images'));
});

gulp.task('build:development', ['clean'], function () {
  environment = 'development';
  gulp.start('sass', 'js');
  gulp.start('copy_template_assets');
  gulp.start('copy_toolkit_assets:images');
});

gulp.task('build:production', ['clean'], function () {
  environment = 'production';
  gulp.start('sass', 'js');
  gulp.start('copy_template_assets');
  gulp.start('copy_toolkit_assets:images');
});
