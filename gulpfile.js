const gulp = require('gulp')
const uglify = require('gulp-uglify')
const del = require('del')
const sass = require('gulp-sass')(require('sass'))
const filelog = require('gulp-filelog')
const include = require('gulp-include')
const colours = require('colors/safe')
const path = require('path')

// Paths
let environment = 'development'
const repoRoot = path.join(__dirname)
const npmRoot = path.join(repoRoot, 'node_modules')
const govukCountryPickerDist = path.join(npmRoot, 'govuk-country-and-territory-autocomplete', 'dist')
const govukToolkitRoot = path.join(npmRoot, 'govuk_frontend_toolkit')
const govukElementsRoot = path.join(npmRoot, 'govuk-elements-sass')
const govukFrontendRoot = path.join(npmRoot, 'govuk-frontend')
const dmToolkitRoot = path.join(npmRoot, 'digitalmarketplace-frontend-toolkit', 'toolkit')
const sspContentRoot = path.join(npmRoot, 'digitalmarketplace-frameworks')
const assetsFolder = path.join(repoRoot, 'app', 'assets')
const staticFolder = path.join(repoRoot, 'app', 'static')
const govukFrontendFontsFolder = path.join(govukFrontendRoot, 'assets', 'fonts')
const govukFrontendImagesFolder = path.join(govukFrontendRoot, 'assets', 'images')

// JavaScript paths
const jsSourceFile = path.join(assetsFolder, 'javascripts', 'application.js')
const jsDistributionFolder = path.join(staticFolder, 'javascripts')
const jsDistributionFile = 'application.js'
const jsPageSpecific = path.join(assetsFolder, 'javascripts', 'page_specific')

// CSS paths
const cssSourceGlob = path.join(assetsFolder, 'scss', 'application*.scss')
const cssDistributionFolder = path.join(staticFolder, 'stylesheets')

// Configuration
const sassOptions = {
  development: {
    outputStyle: 'expanded',
    lineNumbers: true,
    includePaths: [
      path.join(assetsFolder, 'scss'),
      path.join(dmToolkitRoot, 'scss'),
      path.join(govukToolkitRoot, 'stylesheets'),
      path.join(govukElementsRoot, 'public', 'sass')
    ],
    sourceComments: true,
    errLogToConsole: true
  },
  production: {
    outputStyle: 'compressed',
    lineNumbers: true,
    includePaths: [
      path.join(assetsFolder, 'scss'),
      path.join(dmToolkitRoot, 'scss'),
      path.join(govukToolkitRoot, 'stylesheets'),
      path.join(govukElementsRoot, 'public', 'sass')
    ]
  }
}

const uglifyOptions = {
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
}

const logErrorAndExit = function logErrorAndExit (err) {
  const printError = function (type, message) {
    console.log('gulp ' + colours.red('ERR! ') + type + ': ' + message)
  }

  printError('message', err.message)
  printError('file name', err.fileName)
  printError('line number', err.lineNumber)
  process.exit(1)
}

gulp.task('clean:js', function () {
  return del(path.join(jsDistributionFolder, '**', '*')).then(function (paths) {
    console.log('💥  Deleted the following JavaScript files:\n', paths.join('\n'))
  })
})

gulp.task('clean:css', function () {
  return del(path.join(cssDistributionFolder, '**', '*')).then(function (paths) {
    console.log('💥  Deleted the following CSS files:\n', paths.join('\n'))
  })
})

gulp.task('clean', gulp.parallel('clean:js', 'clean:css'))

gulp.task('sass', function () {
  const stream = gulp.src(cssSourceGlob)
    .pipe(filelog('Compressing SCSS files'))
    .pipe(
      sass(sassOptions[environment]))
    .on('error', logErrorAndExit)
    .pipe(gulp.dest(cssDistributionFolder))

  stream.on('end', function () {
    console.log('💾  Compressed CSS saved as .css files in ' + cssDistributionFolder)
  })

  return stream
})

gulp.task('js', function () {
  const stream = gulp.src(jsSourceFile, { sourcemaps: true })
    .pipe(filelog('Compressing JavaScript files'))
    .pipe(include({ hardFail: true }))
    .pipe(uglify(
      uglifyOptions[environment]
    ))
    .pipe(gulp.dest(jsDistributionFolder, { sourcemaps: 'maps' }))

  stream.on('end', function () {
    console.log('💾 Compressed JavaScript saved as ' + path.join(jsDistributionFolder, jsDistributionFile))
  })

  return stream
})

function copyFactory (resourceName, sourceFolder, targetFolder) {
  return function () {
    return gulp
      .src(path.join(sourceFolder, '**', '*'), { base: sourceFolder })
      .pipe(gulp.dest(targetFolder))
      .on('end', function () {
        console.log('📂  Copied ' + resourceName)
      })
  }
}

function copyFiletypeFactory (resourceName, sourceFolder, sourceFileExtension, targetFolder) {
  return function () {
    return gulp
      .src(path.join(sourceFolder, '**', '*.' + sourceFileExtension), { base: sourceFolder })
      .pipe(gulp.dest(targetFolder))
      .on('end', function () {
        console.log('📂  Copied ' + resourceName)
      })
  }
}

gulp.task(
  'copy:govuk_frontend_assets:stylesheets',
  copyFiletypeFactory(
    'stylesheets from GOV.UK Frontend',
    govukFrontendRoot,
    'scss',
    path.join('app', 'assets', 'scss', 'govuk')
  )
)

gulp.task(
  'copy:dm_toolkit_assets:stylesheets',
  copyFactory(
    'stylesheets from the Digital Marketplace frontend toolkit',
    path.join(dmToolkitRoot, 'scss'),
    path.join('app', 'assets', 'scss', 'toolkit')
  )
)

gulp.task(
  'copy:dm_toolkit_assets:images',
  copyFactory(
    'images from the Digital Marketplace frontend toolkit',
    path.join(dmToolkitRoot, 'images'),
    path.join(staticFolder, 'images')
  )
)

gulp.task(
  'copy:govuk_toolkit_assets:images',
  copyFactory(
    'images from the GOVUK frontend toolkit',
    path.join(govukToolkitRoot, 'images'),
    path.join(staticFolder, 'images')
  )
)

gulp.task(
  'copy:dm_toolkit_assets:templates',
  copyFactory(
    'templates from the Digital Marketplace frontend toolkit',
    path.join(dmToolkitRoot, 'templates'),
    path.join('app', 'templates', 'toolkit')
  )
)

gulp.task(
  'copy:images',
  copyFactory(
    'image assets from app to static folder',
    path.join(assetsFolder, 'images'),
    path.join(staticFolder, 'images')
  )
)

gulp.task(
  'copy:frameworks',
  copyFactory(
    'frameworks YAML into app folder',
    path.join(sspContentRoot, 'frameworks'),
    path.join('app', 'content', 'frameworks')
  )
)

gulp.task(
  'copy:govuk_frontend_assets:fonts',
  copyFactory(
    'fonts from GOV.UK Frontend assets',
    govukFrontendFontsFolder,
    path.join(staticFolder, 'fonts')
  )
)

gulp.task(
  'copy:govuk_frontend_assets:images',
  copyFactory(
    'images from GOV.UK Frontend assets',
    govukFrontendImagesFolder,
    path.join(staticFolder, 'images')
  )
)

gulp.task(
  'copy:country_picker:jsons',
  copyFiletypeFactory(
    'country picker jsons to static folder',
    govukCountryPickerDist,
    'json',
    staticFolder
  )
)

gulp.task(
  'copy:country_picker:stylesheets',
  copyFiletypeFactory(
    'country picker stylesheets to static folder',
    govukCountryPickerDist,
    'css',
    cssDistributionFolder
  )
)

gulp.task(
  'copy:country_picker_package:javascripts',
  copyFiletypeFactory(
    'country picker package javascripts to static folder',
    govukCountryPickerDist,
    '{js,js.map}',
    jsDistributionFolder
  )
)

gulp.task(
  'copy:page_specific:javascripts',
  copyFactory(
    'page specific javascript to static folder',
    jsPageSpecific,
    jsDistributionFolder
  )
)

gulp.task('set_environment_to_development', function (cb) {
  environment = 'development'
  cb()
})

gulp.task('set_environment_to_production', function (cb) {
  environment = 'production'
  cb()
})

gulp.task('copy', gulp.parallel(
  'copy:frameworks',
  'copy:govuk_toolkit_assets:images',
  'copy:dm_toolkit_assets:stylesheets',
  'copy:dm_toolkit_assets:images',
  'copy:dm_toolkit_assets:templates',
  'copy:images',
  'copy:govuk_frontend_assets:stylesheets',
  'copy:govuk_frontend_assets:fonts',
  'copy:govuk_frontend_assets:images',
  'copy:country_picker:jsons',
  'copy:country_picker:stylesheets',
  'copy:country_picker_package:javascripts',
  'copy:page_specific:javascripts'
))

gulp.task('compile', gulp.series('copy', gulp.parallel('sass', 'js')))

gulp.task('build:development', gulp.series(gulp.parallel('set_environment_to_development', 'clean'), 'compile'))

gulp.task('build:production', gulp.series(gulp.parallel('set_environment_to_production', 'clean'), 'compile'))

gulp.task('watch', gulp.series('build:development', function () {
  const jsWatcher = gulp.watch([path.join(assetsFolder, '**', '*.js')], gulp.series('js'))
  const cssWatcher = gulp.watch([path.join(assetsFolder, '**', '*.scss')], gulp.series('sass'))
  const dmWatcher = gulp.watch([path.join(npmRoot, 'digitalmarketplace-frameworks', '**')], gulp.series('copy:frameworks'))
  const notice = function (event) {
    console.log('File ' + event.path + ' was ' + event.type + ' running tasks...')
  }

  cssWatcher.on('change', notice)
  jsWatcher.on('change', notice)
  dmWatcher.on('change', notice)
}))
