import * as _ from "underscore";
import {del, get, post} from "../gateway";


export default class Base {
    constructor(data=null) {
        this.subscribers = {};
        this.subscriberId = 0;
        
        const model = this.constructor.model;

        if (data) {
            this.unsaved = {};
            this.saved = Object.assign({}, model.attributes, data);
        }
        else {
            this.unsaved = {};
            this.saved   = Object.assign({}, model.attributes);
        }

        _.keys(model.attributes).forEach(key => {
            Object.defineProperty(this, key, {
                get: () => {
                    let v;
                    
                    v = this.unsaved[key];
                    if (!_.isUndefined(v)) {
                        return v;
                    }
                    
                    v = this.saved[key];
                    if (!_.isUndefined(v)) {
                        return v;
                    }
                    
                    return model.attributes[v];
                },
                set: (v) => {
                    if (v === this.saved[key]) {
                        delete this.unsaved[key];
                    }
                    else {
                        this.unsaved[key] = v;
                    }
                    this.notify();
                }
                
            });
        });

        Object.defineProperty(this, 'id', {get: () => this.saved[model.id]});
    }
    
    // Subscribe to changes, returns function for unsubscribing.
    subscribe(cb) {
        const id = this.subscriberId++;
        this.subscribers[id] = cb;
        cb();
        return () => delete this.subscribers[id];
    }
    
    // Notify subscribers that something changed.
    notify() {
        _.values(this.subscribers).forEach(s => s());
    }

    // Reset data to saved state.
    reset() {
        this.unsaved = Object.assign({}, this.saved);
        this.notify();
    }
    
    // Rmove this entity, returns promise.
    remove() {
        if (!this.id) {
            return Promise.resolve(null);
        }
        
        return del({url: this.constructor.model.root + '/' + this.id});
    }

    // Refresh datra from server, requires id in data, returns promise.
    refresh() {
        if (!this.id) {
            throw new Error("Refresh requires id.");
        }
        
        return get({url: this.constructor.model.root + '/' + this.id}).then(d => {
            this.saved = d.data;
            this.unsaved = {};
            this.notify();
        });
    }
    
    // Save or create, returns promise.
    save() {
        const data = Object.assign({}, this.saved, this.unsaved);

        if (this.id) {
            throw new Error("TODO");
        }
        else {
            return post({url: this.constructor.model.root, data}).then(d => {
                this.saved = d.data;
                this.unsaved = {};
                this.notify();
            });
        }
    }
    
    // Returns true if unsaved.
    isUnsaved() {
        return !this.id || this.isDirty();
    }
    
    // Returns true if any field changed.
    isDirty(key) {
        if (!key) {
            return !_.isEmpty(this.unsaved);
        }
        return !_.isUndefined(this.unsaved[key]);
    }
    
    // Return message for remove confirmation.
    removeConfirmMessage() {
        throw new Error(`removeConfirmMessage not implemented in ${this.constructor.name}`);
    }
}

