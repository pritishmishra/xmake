function addSuffix(version, suffix){
	if(suffix !== ''){
		return version + suffix;
	}
	else{
		return version;
	}
}

module.exports = function(transform, modify, json_file, suffix, dependencies, devDependencies, relDependencies, relDevDependencies, callback){

	var fs = require('fs');

	fs.readFile(json_file, 'utf8', function (err, data) {
		if (err){
			console.err('could not read ' + json_file + ' for transformation');
		}

		data = JSON.parse(data);

		if(modify){
			data.version = addSuffix(data.version, suffix);
		}

		if(transform){

			var index = 0;

			if(data['dependencies@release'] !== undefined){

				for(index in data['dependencies@release']){
					dependencies.forEach(function(dependency){
						if(dependency.name === index && dependency.level === 'others'){
							data.dependencies[index] = addSuffix(data['dependencies@release'][index], suffix);
						}
					});

				}
				delete data['dependencies@release'];
			}

			if(data['devDependencies@release'] !== undefined){

				for(index in data['devDependencies@release']){
					devDependencies.forEach(function(dependency){
						if(dependency.name === index && dependency.level === 'others'){
							data.devDependencies[index] = addSuffix(data['devDependencies@release'][index], suffix);
						}
					});

				}
				delete data['devDependencies@release'];
			}
		}

		callback(data);
	});
};
