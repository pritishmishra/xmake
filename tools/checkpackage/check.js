var program = require('commander');
var validator = require('validator');
var dep = require('./modules/dependency');
var transform = require('./modules/transform');
var fs = require('fs');

program
  .version(require('./package.json').version)
  .option('-f, --filename <file>', 'specify filename to check dependencies, defaults to package.json')
  .option('-v, --validation <mode>', 'report validation errors on stout (warning) or sterr (error), defaults to warning')
  .option('-d, --dependency <level> ', 'specify allowed dependency level (any combination of "version", "range", "others")', function(val, arr){ arr.push(val); return arr; }, [])
  .option('-s, --suffix <suffix>', 'version suffix for dependencies')
  .option('-m, --modify', 'modify version according to suffix')
  .option('-t, --transform', 'transform package.json file')
  .option('-o, --outfile <file>', 'specify filename to write tranformed file, defaults to filename.transform')
  .parse(process.argv);

//set parameter defaults
function setDefault(parameter, paramDefault){
	if(parameter === undefined || parameter.length === 0){
		return paramDefault;
	}
	else{
		return parameter;
	}
}

program.filename = setDefault(program.filename, 'package.json');
program.validation = setDefault(program.validation, 'warning');
program.dependency = setDefault(program.dependency, ['version', 'range']);
program.suffix = setDefault(program.suffix, '');
program.transform = setDefault(program.transform, false);
program.outfile = setDefault(program.outfile, program.filename + '.transform');

//validate parameters
function validateParameter(validation, parameter, value){
	if(!validation){
		console.error('ERROR: ' + parameter + ' does not support value ' + value);
		console.error('ERROR: run program with -h to see allowed options');
		process.exit(1);
	}
}

validateParameter(validator.isIn(program.validation, ['warning', 'error']), 'validation', program.validation);
program.dependency.forEach(function(dependency){
	validateParameter(validator.isIn(dependency, ['version', 'range', 'others']), 'dependency', dependency);
});
validateParameter(validator.isIn(program.transform, ['true', 'false']), 'transform', program.transform);
validateParameter(validator.isIn(program.transform, ['true', 'false']), 'modify', program.modify);

//start program
console.log('INFO: NPM dependency check');
console.log('INFO: ===============================');
console.log('INFO: Process id:', process.pid);
console.log('INFO: parameter filename: ' + program.filename);
console.log('INFO: parameter validation: ' + program.validation);
console.log('INFO: parameter dependency: ' + JSON.stringify(program.dependency));
console.log('INFO: suffix: ' + program.suffix);
console.log('INFO: transform: ' + program.transform);
console.log('INFO: modify: ' + program.modify);
console.log('INFO: parameter outfile: ' + program.outfile);
console.log('INFO: ===============================');

function validateDependency(validation, dependency, location){
	if(!validation){
		if(program.validation === 'warning'){
			console.info('WARN: dependency ' + dependency + ' not allowed in ' + location);
		}
		else {
			console.error('ERROR: dependency ' + dependency + ' not allowed in ' + location);
		}
		return 1;
	}
	return 0;
}

function runValidation(dependencies, devDependencies){
	var depErrors = 0;

	dependencies.forEach(function(dependency){
		depErrors = depErrors + validateDependency(program.dependency.indexOf(dependency.level) !== -1, dependency.raw, 'dependencies');
	});

	devDependencies.forEach(function(dependency){
		depErrors = depErrors + validateDependency(program.dependency.indexOf(dependency.level) !== -1, dependency.raw, 'devDependencies');
	});

	if(depErrors === 0){
		console.info('INFO: no errors found during validation');
	}
	else{
		if(program.validation === 'warning'){
			console.info('WARN: ' + depErrors + ' errors found during validation');
			process.exit(0);
		}
		else {
			console.error('ERROR: ' + depErrors + ' errors found during validation');
			process.exit(1);
		}
	}
}

//validation of package dependencies
dep.parseFile(program.filename, function(dependencies, devDependencies, relDependencies, relDevDependencies){

	//check release dependencies for transformation
	var depErrors = 0;
	if(program.transform){

		relDependencies.forEach(function(dependency){
			depErrors = depErrors + validateDependency(['version'].indexOf(dependency.level) !== -1, dependency.raw, 'dependencies@release');
		});

		relDevDependencies.forEach(function(dependency){
			depErrors = depErrors + validateDependency(['version'].indexOf(dependency.level) !== -1, dependency.raw, 'devDependencies@release');
		});
	}

	if(program.transform || program.modify){
		if(depErrors === 0){
			console.info('INFO: start transformation');
			transform(program.transform, program.modify, program.filename, program.suffix, dependencies, devDependencies, relDependencies, relDevDependencies, function(json_file){

				dep.parseData(json_file, function(transformDependencies, transformDevDependencies){

					runValidation(transformDependencies, transformDevDependencies);

					fs.writeFile(program.outfile, JSON.stringify(json_file, null, 2), function(err) {
						if(err) {
							console.error('ERROR: could not write tranformed file');
							console.error('ERROR: ' + err);
							process.exit(1);
						} else {
							console.log('INFO: transformation completed');
							process.exit(0);
						}
					});

				});
			});
		}
		else{
			if(program.validation === 'warning'){
				console.info('WARN: ' + depErrors + ' errors found before transformation');
				process.exit(0);
			}
			else {
				console.error('ERROR: ' + depErrors + ' errors found before transformation');
				process.exit(1);
			}
		}
	}
	else {
		runValidation(dependencies, devDependencies);
		process.exit(0);
	}
});
