var gulp = require('gulp');
var uglify = require('gulp-uglify');
var deleteFiles = require('del');
var sass = require('gulp-sass');
var filelog = require('gulp-filelog');
var include = require('gulp-include');
var colours = require('colors/safe');
var jasmine = require('gulp-jasmine-phantom');
var sourcemaps = require('gulp-sourcemaps');

// Paths
var environment;
var repoRoot = __dirname + '/';
var bowerRoot = repoRoot + 'bower_components';
var npmRoot = repoRoot + 'node_modules';
var govukToolkitRoot = npmRoot + '/govuk_frontend_toolkit';
var dmToolkitRoot = bowerRoot + '/digitalmarketplace-frontend-toolkit/toolkit';
var sspContentRoot = bowerRoot + '/digitalmarketplace-frameworks';
var assetsFolder = repoRoot + 'app/assets';
var staticFolder = repoRoot + 'app/static';
var govukTemplateFolder = repoRoot + 'bower_components/govuk_template';
var govukTemplateAssetsFolder = govukTemplateFolder + '/assets';
var govukTemplateLayoutsFolder = govukTemplateFolder + '/views/layouts';

// JavaScript paths
var jsSourceFile = assetsFolder + '/javascripts/application.js';
var jsDistributionFolder = staticFolder + '/javascripts';
var jsDistributionFile = 'application.js';

// CSS paths
var cssSourceGlob = assetsFolder + '/scss/application*.scss';
var cssDistributionFolder = staticFolder + '/stylesheets';

// Configuration
var sassOptions = {
  development: {
    outputStyle: 'expanded',
    lineNumbers: true,
    includePaths: [
      assetsFolder + '/scss',
      dmToolkitRoot + '/scss',
      govukToolkitRoot + '/stylesheets',
    ],
    sourceComments: true,
    errLogToConsole: true
  },
  production: {
    outputStyle: 'compressed',
    lineNumbers: true,
    includePaths: [
      assetsFolder + '/scss',
      dmToolkitRoot + '/scss',
      govukToolkitRoot + '/stylesheets',
    ],
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
    },
    compress: false
  },
  production: {
    mangle: true
  }
};

var logErrorAndExit = function logErrorAndExit(err) {
  var printError = function (type, message) {
    console.log('gulp ' + colours.red('ERR! ') + type + ': ' + message);
  };

  printError('message', err.message);
  printError('file name', err.fileName);
  printError('line number', err.lineNumber);
  process.exit(1);

};

gulp.task('clean', function (cb) {
  var fileTypes = [];
  var complete = function (fileType) {
    fileTypes.push(fileType);
    if (fileTypes.length == 2) {
      cb();
    }
  };
  var logOutputFor = function (fileType) {
    return function (err, paths) {
      if (paths !== undefined) {
        console.log('💥  Deleted the following ' + fileType + ' files:\n', paths.join('\n'));
      }
      complete(fileType);
    };
  };

  deleteFiles(jsDistributionFolder + '/**/*', logOutputFor('JavaScript'));
  deleteFiles(cssDistributionFolder + '/**/*', logOutputFor('CSS'));
});

gulp.task('sass', function () {
  var stream = gulp.src(cssSourceGlob)
    .pipe(filelog('Compressing SCSS files'))
    .pipe(
      sass(sassOptions[environment]))
        .on('error', logErrorAndExit)
    .pipe(gulp.dest(cssDistributionFolder));

  stream.on('end', function () {
    console.log('💾  Compressed CSS saved as .css files in ' + cssDistributionFolder);
  });

  return stream;
});

gulp.task('js', function () {
  var stream = gulp.src(jsSourceFile)
    .pipe(filelog('Compressing JavaScript files'))
    .pipe(include())
    .pipe(sourcemaps.init())
    .pipe(uglify(
      uglifyOptions[environment]
    ))
    .pipe(sourcemaps.write('./maps'))
    .pipe(gulp.dest(jsDistributionFolder));

  stream.on('end', function () {
    console.log('💾 Compressed JavaScript saved as ' + jsDistributionFolder + '/' + jsDistributionFile);
  });

  return stream;
});

function copyFactory(resourceName, sourceFolder, targetFolder) {

  return function() {

    return gulp
      .src(sourceFolder + "/**/*", { base: sourceFolder })
      .pipe(gulp.dest(targetFolder))
      .on('end', function () {
        console.log('📂  Copied ' + resourceName);
      });

  };

}

gulp.task(
  'copy:template_assets:stylesheets',
  copyFactory(
    "GOV.UK template stylesheets",
    govukTemplateAssetsFolder + '/stylesheets',
    staticFolder + '/stylesheets'
  )
);

gulp.task(
  'copy:template_assets:images',
  copyFactory(
    "GOV.UK template images",
    govukTemplateAssetsFolder + '/images',
    staticFolder + '/images'
  )
);

gulp.task(
  'copy:template_assets:javascripts',
  copyFactory(
    'GOV.UK template Javascript files',
    govukTemplateAssetsFolder + '/javascripts',
    staticFolder + '/javascripts'
  )
);

gulp.task(
  'copy:dm_toolkit_assets:stylesheets',
  copyFactory(
    "stylesheets from the Digital Marketplace frontend toolkit",
    dmToolkitRoot + '/scss',
    'app/assets/scss/toolkit'
  )
);

gulp.task(
  'copy:dm_toolkit_assets:images',
  copyFactory(
    "images from the Digital Marketplace frontend toolkit",
    dmToolkitRoot + '/images',
    staticFolder + '/images'
  )
);

gulp.task(
  'copy:govuk_toolkit_assets:images',
  copyFactory(
    "images from the GOVUK frontend toolkit",
    govukToolkitRoot + '/images',
    staticFolder + '/images'
  )
);

gulp.task(
  'copy:dm_toolkit_assets:templates',
  copyFactory(
    "templates from the Digital Marketplace frontend toolkit",
    dmToolkitRoot + '/templates',
    'app/templates/toolkit'
  )
);

gulp.task(
  'copy:images',
  copyFactory(
    "image assets from app to static folder",
    assetsFolder + '/images',
    staticFolder + '/images'
  )
);

gulp.task(
  'copy:govuk_template',
  copyFactory(
    "GOV.UK template into app folder",
    govukTemplateLayoutsFolder,
    'app/templates/govuk'
  )
);

gulp.task(
  'copy:frameworks',
  copyFactory(
    "frameworks YAML into app folder",
    sspContentRoot + '/frameworks', 'app/content/frameworks'
  )
);

gulp.task('test', function () {
  var manifest = require(repoRoot + 'spec/javascripts/manifest.js').manifest;

  manifest.support = manifest.support.map(function (val) {
    return val.replace(/^(\.\.\/){3}/, '');
  });
  manifest.test = manifest.test.map(function (val) {
    return val.replace(/^\.\.\//, 'spec/javascripts/');
  });

  return gulp.src(manifest.test)
    .pipe(jasmine({
      'jasmine': '2.0',
      'integration': true,
      'abortOnFail': true,
      'vendor': manifest.support
    }));
});

gulp.task('watch', ['build:development'], function () {
  var jsWatcher = gulp.watch([ assetsFolder + '/**/*.js' ], ['js']);
  var cssWatcher = gulp.watch([ assetsFolder + '/**/*.scss' ], ['sass']);
  var dmWatcher = gulp.watch([ bowerRoot + '/digitalmarketplace-frameworks/**' ], ['copy:frameworks']);
  var notice = function (event) {
    console.log('File ' + event.path + ' was ' + event.type + ' running tasks...');
  };

  cssWatcher.on('change', notice);
  jsWatcher.on('change', notice);
});

gulp.task('set_environment_to_development', function (cb) {
  environment = 'development';
  cb();
});

gulp.task('set_environment_to_production', function (cb) {
  environment = 'production';
  cb();
});

gulp.task(
  'copy',
  [
    'copy:frameworks',
    'copy:template_assets:images',
    'copy:template_assets:stylesheets',
    'copy:template_assets:javascripts',
    'copy:govuk_toolkit_assets:images',
    'copy:dm_toolkit_assets:stylesheets',
    'copy:dm_toolkit_assets:images',
    'copy:dm_toolkit_assets:templates',
    'copy:images',
    'copy:govuk_template'
  ]
);

gulp.task(
  'compile',
  [
    'copy'
  ],
  function() {
    gulp.start('sass');
    gulp.start('js');
  }
);

gulp.task('build:development', ['set_environment_to_development', 'clean'], function () {
  gulp.start('compile');
});

gulp.task('build:production', ['set_environment_to_production', 'clean'], function () {
  gulp.start('compile');
});
