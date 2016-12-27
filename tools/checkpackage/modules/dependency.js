var readJson = require('read-package-json');
var npa = require('npm-package-arg');

function getDependencyLevel(dep){
	switch(dep.type) {
		//a git repo
		case 'git':
			return 'others';

		//a hosted project, e.g. from github
		case 'hosted':
			return 'others';

		//a tagged version, like "foo@latest"
		case 'tag':
			return 'others';

		//a specific version number, like "foo@1.2.3"
		case 'version':
			return 'version';

		//a version range, like "foo@2.x"
		case 'range':
			return 'range';

		//a local file or folder path
		case 'local':
			return 'others';

		//an http url (presumably to a tgz)
		case 'remote':
			return 'others';
	}
}

function getDependencies(jsonData, type){
	var result = [];
	for(var index in jsonData[type]) {
		var dependency = npa(index + '@' + jsonData[type][index]);
		dependency.level = getDependencyLevel(dependency);
		result.push(dependency);
	}
	return result;
}

module.exports = {
	parseFile: function(json_file, callback){

		readJson(json_file, undefined, false, function (err, data) {
			if (err) {
				console.error('ERROR: Can not read package.json file.');
				console.error('ERROR: ' + err);
				callback([]);
			}
			else {
				callback(getDependencies(data, 'dependencies'), getDependencies(data, 'devDependencies'), getDependencies(data, 'dependencies@release'), getDependencies(data, 'devDependencies@release'));
			}
		});

	},
	parseData: function(data, callback) {
		callback(getDependencies(data, 'dependencies'), getDependencies(data, 'devDependencies'), getDependencies(data, 'dependencies@release'), getDependencies(data, 'devDependencies@release'));
	}
};
