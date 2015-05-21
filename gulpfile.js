var gulp = require('gulp');
var uglify = require('gulp-uglifyjs');
var deleteFiles = require('del');
var sass = require('gulp-sass');
var filelog = require('gulp-filelog');

var environment;
var repoRoot = __dirname + '/';
var bowerRoot = repoRoot + 'bower_components';
var npmRoot = repoRoot + 'node_modules';
var govukToolkitRoot = npmRoot + '/govuk_frontend_toolkit';
var dmToolkitRoot = bowerRoot + '/digitalmarketplace_frontend_toolkit/toolkit';
var assetsFolder = repoRoot + 'app/assets';
var staticFolder = repoRoot + 'app/static';
var govukTemplateAssetsFolder = repoRoot + 'bower_components/govuk_template/assets';

// JavaScript paths
var jsVendorFiles = [
  govukToolkitRoot + '/javascripts/govuk/analytics/tracker.js',
  govukToolkitRoot + '/javascripts/govuk/analytics/google-analytics-universal-tracker.js',
  govukToolkitRoot + '/javascripts/govuk/analytics/google-analytics-classic-tracker.js',
];
var jsSourceFiles = [
  assetsFolder + '/javascripts/_analytics.js',
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
    includePaths: [
      assetsFolder + '/scss',
      govukToolkitRoot + '/stylesheets',
      dmToolkitRoot + '/scss'
    ],
    sourceComments: true,
    errLogToConsole: true
  },
  production: {
    outputStyle: 'compressed',
    lineNumbers: true,
    includePaths: [
      assetsFolder + '/scss',
      govukToolkitRoot + '/stylesheets',
      dmToolkitRoot + '/scss'
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
        console.log('Deleted the following ' + fileType + ' files:\n', paths.join('\n'));
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
    .pipe(sass(sassOptions[environment]))
    .on('error', function (err) {
      console.log(err.message);
    })
    .pipe(gulp.dest(cssDistributionFolder));

  stream.on('end', function () {
    console.log('Compressed CSS saved as .css files in ' + cssDistributionFolder)
  });

  return stream;
});

gulp.task('js', function () {
  // produce full array of JS files from vendor + local scripts
  jsFiles = jsVendorFiles.concat(jsSourceFiles);
  var stream = gulp.src(jsFiles)
    .pipe(filelog('Compressing JavaScript files'))
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
  stream = gulp.src(govukTemplateAssetsFolder + '/stylesheets/**/*', { base : govukTemplateAssetsFolder + '/stylesheets' })
    .pipe(gulp.dest(staticFolder + '/stylesheets'))

  stream.on('end', function () {
    console.log('Copied CSS assets from the govuk template');
  });

  return stream;
});

gulp.task('copy_template_assets:images', function () {
  stream = gulp.src(govukTemplateAssetsFolder + '/images/**/*', { base : govukTemplateAssetsFolder + '/images' })
    .pipe(gulp.dest(staticFolder + '/images'))

  stream.on('end', function () {
    console.log('Copied image assets from the govuk template');
  });

  return stream;
});

gulp.task('copy_template_assets:javascripts', function () {
  stream = gulp.src(govukTemplateAssetsFolder + '/javascripts/**/*', { base : govukTemplateAssetsFolder + '/javascripts' })
    .pipe(gulp.dest(staticFolder + '/javascripts'))

  stream.on('end', function () {
    console.log('Copied JS assets from the govuk template');
  });

  return stream;
});

gulp.task('copy_dm_toolkit_assets:images', function () {
  stream = gulp.src(dmToolkitRoot + '/images/**/*', { base : dmToolkitRoot + '/images' })
    .pipe(gulp.dest(staticFolder + '/images'))

  stream.on('end', function () {
    console.log('Copied image assets from the digital marketplace front-end toolkit');
  });

  return stream;
});

gulp.task('copy_template_assets', [
  'copy_template_assets:stylesheets',
  'copy_template_assets:images',
  'copy_template_assets:javascripts'
]);

gulp.task('copy:images', function () {
  stream = gulp.src(assetsFolder + '/images/**/*', { base : assetsFolder + '/images' })
    .pipe(gulp.dest(staticFolder + '/images'))

  stream.on('end', function () {
    console.log('Copied image assets into static folder');
  });

  return stream;
});

gulp.task('copy_dm_toolkit_assets', ['copy_dm_toolkit_assets:images']);

gulp.task('watch', ['build:development'], function () {
  var jsWatcher = gulp.watch([ assetsFolder + '/**/*.js' ], ['js']);
  var cssWatcher = gulp.watch([ assetsFolder + '/**/*.scss' ], ['sass']);
  var notice = function (event) {
    console.log('File ' + event.path + ' was ' + event.type + ' running tasks...');
  }

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

gulp.task('copy_and_compile', ['sass', 'js', 'copy_template_assets', 'copy_dm_toolkit_assets']);

gulp.task('build:development', ['set_environment_to_development', 'clean'], function () {
  gulp.start('sass', 'js');
  gulp.start('copy:images');
  gulp.start('copy_template_assets');
  gulp.start('copy_dm_toolkit_assets');
});

gulp.task('build:production', ['set_environment_to_production', 'clean'], function () {
  gulp.start('sass', 'js');
  gulp.start('copy:images');
  gulp.start('copy_template_assets');
  gulp.start('copy_dm_toolkit_assets');
});
